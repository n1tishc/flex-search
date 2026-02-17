import json
import pytest
import pytest_asyncio
import aiosqlite
from pathlib import Path
from unittest.mock import patch

from app.db.connection import init_db, close_db, get_db


@pytest_asyncio.fixture
async def db():
    """Initialize an in-memory SQLite DB for tests."""
    with patch("app.config.settings") as mock_settings:
        mock_settings.db_path = ":memory:"
        mock_settings.repos_csv_path = "repos.csv"
        mock_settings.text_score_weight = 0.65
        mock_settings.fixability_score_weight = 0.35
        mock_settings.max_concurrency = 15
        mock_settings.github_token = ""
        mock_settings.github_api_base = "https://api.github.com"

        # We need to patch at the connection module level too
        with patch("app.db.connection.settings", mock_settings):
            await init_db()
            conn = await get_db()
            yield conn
            await close_db()


@pytest_asyncio.fixture
async def seeded_db(db):
    """DB with sample repos, issues, comments, and features."""
    # Insert a repo
    await db.execute(
        """INSERT INTO repos (repo_id, full_name, owner, name, stars, forks,
                              open_issues_count, language, pushed_at, archived, last_synced_at)
           VALUES (1, 'owner/repo', 'owner', 'repo', 1000, 100, 50, 'Python',
                   '2026-02-15T00:00:00Z', 0, '2026-02-17T00:00:00Z')"""
    )

    # Insert issues
    await db.execute(
        """INSERT INTO issues (issue_id, repo_id, number, title, body, state,
                               user_login, labels, comments_count, html_url,
                               created_at, updated_at)
           VALUES (101, 1, 42, 'TypeError when calling parse()',
                   '## Steps to reproduce\n\n```python\nresult = parse(None)\n```\n\nExpected behavior: should return empty.',
                   'open', 'testuser', ?, 5,
                   'https://github.com/owner/repo/issues/42',
                   '2026-02-01T00:00:00Z', '2026-02-10T00:00:00Z')""",
        (json.dumps(["bug", "good first issue"]),),
    )

    await db.execute(
        """INSERT INTO issues (issue_id, repo_id, number, title, body, state,
                               user_login, labels, comments_count, html_url,
                               created_at, updated_at, closed_at)
           VALUES (102, 1, 43, 'Fix null pointer in handler',
                   'Null pointer when handler is None.',
                   'closed', 'dev1', ?, 12,
                   'https://github.com/owner/repo/issues/43',
                   '2026-01-01T00:00:00Z', '2026-01-15T00:00:00Z', '2026-01-15T00:00:00Z')""",
        (json.dumps(["bug"]),),
    )

    # Insert a comment with maintainer association
    await db.execute(
        """INSERT INTO comments (comment_id, issue_id, body, user_login,
                                 author_association, created_at)
           VALUES (201, 101, 'Looking into this.', 'maintainer1', 'MEMBER',
                   '2026-02-02T00:00:00Z')"""
    )

    # Insert issue features
    await db.execute(
        """INSERT INTO issue_features (issue_id, fixability_score, grade, reasons, features, computed_at)
           VALUES (101, 76, 'B', ?, ?, '2026-02-10T00:00:00Z')""",
        (
            json.dumps(["+8 steps to reproduce", "+3 code block", "+10 maintainer replied"]),
            json.dumps({
                "has_steps_to_reproduce": True,
                "has_expected_vs_actual": True,
                "has_stack_trace": False,
                "has_code_block": True,
                "env_detail_count": 0,
                "maintainer_replied": True,
                "labels": ["bug", "good first issue"],
                "state": "open",
                "comments_count": 5,
                "days_old": 16,
            }),
        ),
    )

    await db.execute(
        """INSERT INTO issue_features (issue_id, fixability_score, grade, reasons, features, computed_at)
           VALUES (102, 23, 'D', ?, ?, '2026-01-15T00:00:00Z')""",
        (
            json.dumps(["-10 closed"]),
            json.dumps({
                "has_steps_to_reproduce": False,
                "has_expected_vs_actual": False,
                "has_stack_trace": False,
                "has_code_block": False,
                "env_detail_count": 0,
                "maintainer_replied": False,
                "labels": ["bug"],
                "state": "closed",
                "comments_count": 12,
                "days_old": 47,
            }),
        ),
    )

    await db.commit()
    yield db


@pytest.fixture
def sample_issue():
    return {
        "number": 42,
        "title": "TypeError when calling parse()",
        "html_url": "https://github.com/owner/repo/issues/42",
        "state": "open",
        "created_at": "2026-02-01T00:00:00Z",
        "updated_at": "2026-02-10T00:00:00Z",
        "comments": 5,
        "labels": [{"name": "bug"}, {"name": "good first issue"}],
        "user": {"login": "testuser"},
        "body": "## Steps to reproduce\n\n```python\nresult = parse(None)\n```\n\nExpected behavior: should return empty.",
        "repository_url": "https://api.github.com/repos/owner/repo",
    }


@pytest.fixture
def sample_closed_issue():
    return {
        "number": 43,
        "title": "Fix null pointer in handler",
        "html_url": "https://github.com/owner/repo/issues/43",
        "state": "closed",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-15T00:00:00Z",
        "closed_at": "2026-01-15T00:00:00Z",
        "comments": 12,
        "labels": [{"name": "bug"}],
        "user": {"login": "dev1"},
        "body": "Null pointer when handler is None.",
        "repository_url": "https://api.github.com/repos/owner/repo",
    }
