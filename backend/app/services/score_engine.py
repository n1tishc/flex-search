from __future__ import annotations

from app.services.feature_service import compute_score_from_features


def breakdown_from_features(score: float, features: dict) -> dict:
    """Map additive score + features back to the 3-bucket breakdown the frontend expects.

    The original frontend expects repo_health, issue_signals, code_context each as 0.0-1.0.
    We approximate these from the additive features.
    """
    normalized = score / 100.0

    # Approximate repo_health from state-related signals
    repo_health = 0.0
    if features.get("state") == "open":
        repo_health += 0.3
    if features.get("maintainer_replied"):
        repo_health += 0.4
    comments = features.get("comments_count", 0)
    if comments >= 3:
        repo_health += 0.3
    elif comments >= 1:
        repo_health += 0.15
    repo_health = min(1.0, repo_health)

    # Approximate issue_signals from labels and engagement
    issue_signals = 0.0
    labels = {l.lower() for l in features.get("labels", [])}
    if "good first issue" in labels:
        issue_signals += 0.3
    if "help wanted" in labels:
        issue_signals += 0.25
    if "bug" in labels:
        issue_signals += 0.15
    if features.get("maintainer_replied"):
        issue_signals += 0.3
    issue_signals = min(1.0, issue_signals)

    # Approximate code_context from text quality signals
    code_context = 0.0
    if features.get("has_steps_to_reproduce"):
        code_context += 0.3
    if features.get("has_expected_vs_actual"):
        code_context += 0.2
    if features.get("has_stack_trace"):
        code_context += 0.2
    if features.get("has_code_block"):
        code_context += 0.15
    env = features.get("env_detail_count", 0)
    if env >= 2:
        code_context += 0.15
    elif env >= 1:
        code_context += 0.08
    code_context = min(1.0, code_context)

    return {
        "score": round(normalized, 4),
        "grade": _grade(normalized),
        "breakdown": {
            "repo_health": round(repo_health, 4),
            "issue_signals": round(issue_signals, 4),
            "code_context": round(code_context, 4),
        },
        "enriched": True,
    }


def compute_fixability_from_db(
    fixability_score: float, grade: str, features: dict
) -> dict:
    """Build a fixability result dict from pre-computed DB data."""
    result = breakdown_from_features(fixability_score, features)
    result["score"] = round(fixability_score / 100.0, 4)
    result["grade"] = grade
    return result


def _grade(score: float) -> str:
    if score >= 0.80:
        return "A"
    if score >= 0.60:
        return "B"
    if score >= 0.40:
        return "C"
    if score >= 0.20:
        return "D"
    return "F"
