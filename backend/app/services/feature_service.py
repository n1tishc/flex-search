from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.db import queries
from app.utils.text_analysis import extract_features

logger = logging.getLogger(__name__)

MAINTAINER_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}

NEGATIVE_LABELS = {"wontfix", "won't fix", "invalid", "duplicate"}
BLOCKED_LABELS = {"blocked", "waiting", "waiting-for-author", "needs-more-info"}


def compute_score_from_features(features: dict) -> tuple[float, str, list[str]]:
    """Compute additive fixability score from features dict.

    Returns (score_0_100, grade, reasons).
    """
    score = 50.0
    reasons: list[str] = []

    # Positive text signals
    if features.get("has_steps_to_reproduce"):
        score += 8
        reasons.append("+8 steps to reproduce")
    if features.get("has_expected_vs_actual"):
        score += 5
        reasons.append("+5 expected vs actual")
    if features.get("has_stack_trace"):
        score += 4
        reasons.append("+4 stack trace")
    if features.get("has_code_block"):
        score += 3
        reasons.append("+3 code block")

    env_count = features.get("env_detail_count", 0)
    if env_count >= 2:
        score += 4
        reasons.append("+4 env details (2+)")
    elif env_count == 1:
        score += 2
        reasons.append("+2 env detail (1)")

    # Maintainer engagement
    if features.get("maintainer_replied"):
        score += 10
        reasons.append("+10 maintainer replied")

    # Labels
    labels = {l.lower() for l in features.get("labels", [])}

    if "good first issue" in labels:
        score += 8
        reasons.append("+8 good first issue label")
    if "help wanted" in labels:
        score += 6
        reasons.append("+6 help wanted label")
    if "bug" in labels:
        score += 3
        reasons.append("+3 bug label")

    # Comment activity
    state = features.get("state", "open")
    comments = features.get("comments_count", 0)
    if state == "open":
        if comments >= 3:
            score += 5
            reasons.append("+5 active discussion (3+ comments)")
        elif comments >= 1:
            score += 2
            reasons.append("+2 some discussion")

    # Negative signals
    if labels & BLOCKED_LABELS:
        score -= 15
        reasons.append("-15 blocked/waiting label")
    if labels & NEGATIVE_LABELS:
        score -= 20
        reasons.append("-20 wontfix/invalid/duplicate label")
    if state == "closed":
        score -= 10
        reasons.append("-10 closed")

    # Staleness
    days_old = features.get("days_old", 0)
    if days_old >= 180:
        score -= 8
        reasons.append("-8 stale (180+ days)")
    elif days_old >= 90:
        score -= 4
        reasons.append("-4 aging (90+ days)")

    score = max(0.0, min(100.0, score))

    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    elif score >= 20:
        grade = "D"
    else:
        grade = "F"

    return score, grade, reasons


def _days_since(iso_date: str | None) -> float:
    if not iso_date:
        return 0.0
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
    except Exception:
        return 0.0


async def score_all_dirty() -> int:
    """Score all issues that need (re)scoring. Returns count scored."""
    dirty = await queries.get_dirty_issues()
    count = 0

    for row in dirty:
        issue_id = row["issue_id"]
        body = row["body"] or ""
        labels = json.loads(row["labels"]) if row["labels"] else []

        # Extract text features from body
        text_features = extract_features(body)

        # Check for maintainer replies in comments
        from app.db.connection import get_db
        db = await get_db()
        cursor = await db.execute(
            """SELECT 1 FROM comments
               WHERE issue_id = ? AND author_association IN ('OWNER', 'MEMBER', 'COLLABORATOR')
               LIMIT 1""",
            (issue_id,),
        )
        maintainer_row = await cursor.fetchone()

        # Build combined features dict
        features = {
            **text_features,
            "maintainer_replied": maintainer_row is not None,
            "labels": labels,
            "state": row["state"],
            "comments_count": row["comments_count"],
            "days_old": _days_since(row["created_at"]),
        }

        score, grade, reasons = compute_score_from_features(features)

        await queries.upsert_issue_features(
            issue_id=issue_id,
            fixability_score=score,
            grade=grade,
            reasons=reasons,
            features=features,
        )
        count += 1

    logger.info("Scored %d issues", count)
    return count
