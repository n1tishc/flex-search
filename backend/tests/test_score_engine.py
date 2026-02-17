from app.services.feature_service import compute_score_from_features
from app.services.score_engine import breakdown_from_features, compute_fixability_from_db


def test_base_score_no_signals():
    features = {
        "has_steps_to_reproduce": False,
        "has_expected_vs_actual": False,
        "has_stack_trace": False,
        "has_code_block": False,
        "env_detail_count": 0,
        "maintainer_replied": False,
        "labels": [],
        "state": "open",
        "comments_count": 0,
        "days_old": 10,
    }
    score, grade, reasons = compute_score_from_features(features)
    assert score == 50.0
    assert grade == "C"
    assert reasons == []


def test_positive_signals_boost():
    features = {
        "has_steps_to_reproduce": True,
        "has_expected_vs_actual": True,
        "has_stack_trace": True,
        "has_code_block": True,
        "env_detail_count": 3,
        "maintainer_replied": True,
        "labels": ["bug", "good first issue", "help wanted"],
        "state": "open",
        "comments_count": 5,
        "days_old": 10,
    }
    score, grade, reasons = compute_score_from_features(features)
    # 50 + 8 + 5 + 4 + 3 + 4 + 10 + 8 + 6 + 3 + 5 = 106 → clamped to 100
    assert score == 100.0
    assert grade == "A"


def test_negative_signals_drop():
    features = {
        "has_steps_to_reproduce": False,
        "has_expected_vs_actual": False,
        "has_stack_trace": False,
        "has_code_block": False,
        "env_detail_count": 0,
        "maintainer_replied": False,
        "labels": ["wontfix"],
        "state": "closed",
        "comments_count": 0,
        "days_old": 200,
    }
    score, grade, reasons = compute_score_from_features(features)
    # 50 - 20 - 10 - 8 = 12
    assert score == 12.0
    assert grade == "F"


def test_closed_issue_penalty():
    features = {
        "has_steps_to_reproduce": False,
        "has_expected_vs_actual": False,
        "has_stack_trace": False,
        "has_code_block": False,
        "env_detail_count": 0,
        "maintainer_replied": False,
        "labels": [],
        "state": "closed",
        "comments_count": 0,
        "days_old": 10,
    }
    score, grade, reasons = compute_score_from_features(features)
    assert score == 40.0
    assert grade == "C"
    assert "-10 closed" in reasons


def test_good_first_issue_label():
    features = {
        "has_steps_to_reproduce": False,
        "has_expected_vs_actual": False,
        "has_stack_trace": False,
        "has_code_block": False,
        "env_detail_count": 0,
        "maintainer_replied": False,
        "labels": ["good first issue"],
        "state": "open",
        "comments_count": 0,
        "days_old": 10,
    }
    score, grade, reasons = compute_score_from_features(features)
    assert score == 58.0
    assert "+8 good first issue label" in reasons


def test_stale_penalty():
    features = {
        "has_steps_to_reproduce": False,
        "has_expected_vs_actual": False,
        "has_stack_trace": False,
        "has_code_block": False,
        "env_detail_count": 0,
        "maintainer_replied": False,
        "labels": [],
        "state": "open",
        "comments_count": 0,
        "days_old": 200,
    }
    score, grade, reasons = compute_score_from_features(features)
    assert score == 42.0
    assert "-8 stale (180+ days)" in reasons


def test_aging_penalty():
    features = {
        "has_steps_to_reproduce": False,
        "has_expected_vs_actual": False,
        "has_stack_trace": False,
        "has_code_block": False,
        "env_detail_count": 0,
        "maintainer_replied": False,
        "labels": [],
        "state": "open",
        "comments_count": 0,
        "days_old": 100,
    }
    score, grade, reasons = compute_score_from_features(features)
    assert score == 46.0
    assert "-4 aging (90+ days)" in reasons


def test_breakdown_from_features():
    features = {
        "has_steps_to_reproduce": True,
        "has_expected_vs_actual": True,
        "has_stack_trace": False,
        "has_code_block": True,
        "env_detail_count": 1,
        "maintainer_replied": True,
        "labels": ["bug", "good first issue"],
        "state": "open",
        "comments_count": 5,
        "days_old": 10,
    }
    result = breakdown_from_features(76, features)
    assert 0 <= result["score"] <= 1.0
    assert result["grade"] in ("A", "B", "C", "D", "F")
    assert "breakdown" in result
    bd = result["breakdown"]
    assert 0 <= bd["repo_health"] <= 1.0
    assert 0 <= bd["issue_signals"] <= 1.0
    assert 0 <= bd["code_context"] <= 1.0
    assert result["enriched"] is True


def test_compute_fixability_from_db():
    features = {
        "has_steps_to_reproduce": True,
        "maintainer_replied": True,
        "labels": ["bug"],
        "state": "open",
        "comments_count": 3,
    }
    result = compute_fixability_from_db(76.0, "B", features)
    assert result["score"] == 0.76
    assert result["grade"] == "B"
    assert result["enriched"] is True
