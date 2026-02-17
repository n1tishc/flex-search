from __future__ import annotations

import json
import logging

from app.db import queries
from app.models.schemas import (
    FixabilityBreakdown,
    FixabilityResult,
    IssueResult,
    RateLimitInfo,
    RepoSummary,
    ScoredIssue,
    SearchRequest,
    SearchResponse,
)
from app.services.github_client import github_client
from app.services.score_engine import compute_fixability_from_db

logger = logging.getLogger(__name__)


def _row_to_scored_issue(row) -> ScoredIssue:
    labels = json.loads(row["labels"]) if row["labels"] else []
    features = json.loads(row["features"]) if row["features"] else {}
    body = row["body"] or ""

    fix = compute_fixability_from_db(
        fixability_score=row["fixability_score"],
        grade=row["grade"],
        features=features,
    )

    issue = IssueResult(
        number=row["number"],
        title=row["title"],
        html_url=row["html_url"],
        state=row["state"],
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
        comments=row["comments_count"],
        labels=labels,
        user=row["user_login"],
        body_snippet=body[:300],
        repo_full_name=row["repo_full_name"],
    )

    repo_summary = RepoSummary(
        full_name=row["repo_full_name"],
        stars=row["stars"],
        open_issues=row["open_issues_count"],
        language=row["language"],
        pushed_at=row["pushed_at"],
        archived=bool(row["archived"]),
    )

    return ScoredIssue(
        issue=issue,
        repo_summary=repo_summary,
        fixability=FixabilityResult(
            score=fix["score"],
            grade=fix["grade"],
            breakdown=FixabilityBreakdown(**fix["breakdown"]),
            enriched=fix["enriched"],
        ),
    )


async def search_issues(req: SearchRequest) -> SearchResponse:
    offset = (req.page - 1) * req.per_page

    try:
        rows, total_count = await queries.search_issues_fts(
            query=req.query,
            language=req.language,
            state=req.state,
            labels=req.labels,
            sort_by=req.sort_by,
            limit=req.per_page,
            offset=offset,
        )
    except Exception:
        logger.exception("FTS search failed for query: %s", req.query)
        rows, total_count = [], 0

    scored_items = [_row_to_scored_issue(row) for row in rows]

    rl = github_client.rate_limit
    return SearchResponse(
        total_count=total_count,
        items=scored_items,
        rate_limit=RateLimitInfo(
            remaining=rl.remaining,
            limit=rl.limit,
            reset_at=rl.reset_at.isoformat() if rl.reset_at else None,
        ),
    )
