from __future__ import annotations

import csv
import logging
from pathlib import Path

from app.config import settings
from app.db import queries
from app.services.github_client import github_client

logger = logging.getLogger(__name__)

MAINTAINER_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


class IngestionService:
    def __init__(self) -> None:
        self._client = github_client

    async def load_repos_from_csv(self, csv_path: str | None = None) -> list[tuple[str, str]]:
        """Read owner/repo pairs from CSV. Returns list of (owner, repo) tuples."""
        path = Path(csv_path or settings.repos_csv_path)
        repos: list[tuple[str, str]] = []
        with open(path) as f:
            reader = csv.reader(f)
            for row in reader:
                line = row[0].strip() if row else ""
                if "/" in line and not line.startswith("#"):
                    owner, name = line.split("/", 1)
                    repos.append((owner.strip(), name.strip()))
        return repos

    async def sync_repo_metadata(self, owner: str, name: str) -> int | None:
        """Fetch and upsert repo metadata. Returns repo_id or None on failure."""
        try:
            raw = await self._client.get_repo(owner, name)
            repo_id = raw["id"]
            await queries.upsert_repo(
                repo_id=repo_id,
                full_name=raw.get("full_name", f"{owner}/{name}"),
                owner=owner,
                name=name,
                stars=raw.get("stargazers_count", 0),
                forks=raw.get("forks_count", 0),
                open_issues_count=raw.get("open_issues_count", 0),
                language=raw.get("language"),
                pushed_at=raw.get("pushed_at"),
                updated_at=raw.get("updated_at"),
                archived=raw.get("archived", False),
            )
            logger.info("Synced repo %s/%s (id=%d)", owner, name, repo_id)
            return repo_id
        except Exception:
            logger.exception("Failed to sync repo %s/%s", owner, name)
            return None

    async def sync_issues(self, owner: str, name: str, repo_id: int, max_pages: int = 5) -> int:
        """Fetch open issues for a repo and upsert them. Returns count of issues synced."""
        count = 0
        for page in range(1, max_pages + 1):
            try:
                resp = await self._client.get(
                    f"/repos/{owner}/{name}/issues",
                    params={
                        "state": "all",
                        "per_page": 100,
                        "page": page,
                        "sort": "updated",
                        "direction": "desc",
                    },
                )
                items = resp.json()
                if not items:
                    break
                for item in items:
                    # Skip pull requests (they also appear in /issues)
                    if item.get("pull_request"):
                        continue
                    labels = [
                        lbl.get("name", "") if isinstance(lbl, dict) else str(lbl)
                        for lbl in item.get("labels", [])
                    ]
                    await queries.upsert_issue(
                        issue_id=item["id"],
                        repo_id=repo_id,
                        number=item["number"],
                        title=item.get("title", ""),
                        body=item.get("body") or "",
                        state=item.get("state", "open"),
                        user_login=item.get("user", {}).get("login", ""),
                        labels=labels,
                        comments_count=item.get("comments", 0),
                        html_url=item.get("html_url", ""),
                        created_at=item.get("created_at"),
                        updated_at=item.get("updated_at"),
                        closed_at=item.get("closed_at"),
                    )
                    count += 1
            except Exception:
                logger.exception("Failed to fetch issues page %d for %s/%s", page, owner, name)
                break
        logger.info("Synced %d issues for %s/%s", count, owner, name)
        return count

    async def sync_comments_for_issue(
        self, owner: str, name: str, issue_number: int, issue_id: int
    ) -> int:
        """Fetch and upsert comments for a single issue. Returns count."""
        count = 0
        try:
            resp = await self._client.get(
                f"/repos/{owner}/{name}/issues/{issue_number}/comments",
                params={"per_page": 100},
            )
            comments = resp.json()
            if not isinstance(comments, list):
                return 0
            for c in comments:
                await queries.upsert_comment(
                    comment_id=c["id"],
                    issue_id=issue_id,
                    body=c.get("body") or "",
                    user_login=c.get("user", {}).get("login", ""),
                    author_association=c.get("author_association", ""),
                    created_at=c.get("created_at"),
                    updated_at=c.get("updated_at"),
                )
                count += 1
        except Exception:
            logger.exception(
                "Failed to fetch comments for %s/%s#%d", owner, name, issue_number
            )
        return count

    async def run_full_sync(self, csv_path: str | None = None) -> dict:
        """Run a full sync: repos → issues → comments. Returns summary stats."""
        repos_list = await self.load_repos_from_csv(csv_path)
        stats = {"repos": 0, "issues": 0, "comments": 0}

        for owner, name in repos_list:
            repo_id = await self.sync_repo_metadata(owner, name)
            if repo_id is None:
                continue
            stats["repos"] += 1

            issue_count = await self.sync_issues(owner, name, repo_id)
            stats["issues"] += issue_count

            # Fetch comments for issues with comments
            from app.db.connection import get_db
            db = await get_db()
            cursor = await db.execute(
                "SELECT issue_id, number FROM issues WHERE repo_id = ? AND comments_count > 0",
                (repo_id,),
            )
            issues_with_comments = await cursor.fetchall()
            for row in issues_with_comments:
                comment_count = await self.sync_comments_for_issue(
                    owner, name, row["number"], row["issue_id"]
                )
                stats["comments"] += comment_count

        logger.info("Full sync complete: %s", stats)
        return stats
