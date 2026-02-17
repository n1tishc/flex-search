from __future__ import annotations

import httpx
from datetime import datetime, timezone

from app.config import settings


class RateLimitTracker:
    def __init__(self) -> None:
        self.remaining: int = -1
        self.limit: int = -1
        self.reset_at: datetime | None = None

    def update(self, headers: httpx.Headers) -> None:
        if "x-ratelimit-remaining" in headers:
            self.remaining = int(headers["x-ratelimit-remaining"])
        if "x-ratelimit-limit" in headers:
            self.limit = int(headers["x-ratelimit-limit"])
        if "x-ratelimit-reset" in headers:
            ts = int(headers["x-ratelimit-reset"])
            self.reset_at = datetime.fromtimestamp(ts, tz=timezone.utc)

    @property
    def budget_mode(self) -> str:
        if self.remaining < 0:
            return "full"
        if self.remaining > 200:
            return "full"
        if self.remaining > 50:
            return "conserve"
        return "minimal"

    def to_dict(self) -> dict:
        return {
            "remaining": self.remaining,
            "limit": self.limit,
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
        }


class GitHubClient:
    def __init__(self) -> None:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self._client = httpx.AsyncClient(
            base_url=settings.github_api_base,
            headers=headers,
            timeout=30.0,
        )
        self.rate_limit = RateLimitTracker()

    async def get(self, url: str, params: dict | None = None) -> httpx.Response:
        resp = await self._client.get(url, params=params)
        self.rate_limit.update(resp.headers)
        resp.raise_for_status()
        return resp

    async def search_issues(
        self, query: str, page: int = 1, per_page: int = 30
    ) -> dict:
        resp = await self.get(
            "/search/issues",
            params={"q": query, "page": page, "per_page": per_page},
        )
        return resp.json()

    async def get_repo(self, owner: str, repo: str) -> dict:
        resp = await self.get(f"/repos/{owner}/{repo}")
        return resp.json()

    async def get_contributor_count(self, owner: str, repo: str) -> int:
        resp = await self.get(
            f"/repos/{owner}/{repo}/contributors",
            params={"per_page": 1, "anon": "true"},
        )
        link = resp.headers.get("link", "")
        if 'rel="last"' in link:
            for part in link.split(","):
                if 'rel="last"' in part:
                    url_part = part.split(";")[0].strip().strip("<>")
                    if "page=" in url_part:
                        page_str = url_part.split("page=")[-1].split("&")[0]
                        return int(page_str)
        return len(resp.json()) if resp.status_code == 200 else 0

    async def get_issue_timeline(
        self, owner: str, repo: str, issue_number: int
    ) -> list[dict]:
        resp = await self.get(
            f"/repos/{owner}/{repo}/issues/{issue_number}/timeline",
            params={"per_page": 100},
        )
        return resp.json()

    async def get_rate_limit(self) -> dict:
        resp = await self.get("/rate_limit")
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()


# Singleton
github_client = GitHubClient()
