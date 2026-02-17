from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.db import queries
from app.models.schemas import (
    FixabilityBreakdown,
    FixabilityResult,
    IssueDetailResponse,
    IssueResult,
    RepoSummary,
)
from app.services.score_engine import compute_fixability_from_db

router = APIRouter()


@router.get("/issue/{owner}/{repo}/{number}", response_model=IssueDetailResponse)
async def issue_detail(owner: str, repo: str, number: int) -> IssueDetailResponse:
    row = await queries.get_issue_by_repo_and_number(owner, repo, number)
    if row is None:
        raise HTTPException(status_code=404, detail="Issue not found")

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

    # Fetch comments for timeline events
    comments = await queries.get_comments_for_issue(row["issue_id"])
    timeline_events = [
        {
            "event": "commented",
            "user": c["user_login"],
            "author_association": c["author_association"],
            "body": (c["body"] or "")[:200],
            "created_at": c["created_at"],
        }
        for c in comments
    ]

    return IssueDetailResponse(
        issue=issue,
        repo_summary=repo_summary,
        fixability=FixabilityResult(
            score=fix["score"],
            grade=fix["grade"],
            breakdown=FixabilityBreakdown(**fix["breakdown"]),
            enriched=fix["enriched"],
        ),
        linked_prs=[],
        similar_closed=[],
        timeline_events=timeline_events[:20],
    )
