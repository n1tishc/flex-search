import pytest

from app.services.feature_service import score_all_dirty


@pytest.mark.asyncio
async def test_score_all_dirty_scores_unscored(db):
    """Issues without features should get scored."""
    import json

    # Insert a repo and issue without features
    await db.execute(
        """INSERT INTO repos (repo_id, full_name, owner, name, stars, forks,
                              open_issues_count, language, pushed_at, archived)
           VALUES (1, 'test/repo', 'test', 'repo', 100, 10, 5, 'Python',
                   '2026-02-15T00:00:00Z', 0)"""
    )
    await db.execute(
        """INSERT INTO issues (issue_id, repo_id, number, title, body, state,
                               user_login, labels, comments_count, html_url,
                               created_at, updated_at)
           VALUES (201, 1, 1, 'Test issue', 'Some body text', 'open', 'user1',
                   ?, 2, 'https://github.com/test/repo/issues/1',
                   '2026-02-01T00:00:00Z', '2026-02-10T00:00:00Z')""",
        (json.dumps(["bug"]),),
    )
    await db.commit()

    count = await score_all_dirty()
    assert count == 1

    # Verify features were created
    cursor = await db.execute(
        "SELECT fixability_score, grade FROM issue_features WHERE issue_id = 201"
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] > 0  # Should have a score
    assert row[1] in ("A", "B", "C", "D", "F")


@pytest.mark.asyncio
async def test_score_all_dirty_skips_scored(seeded_db):
    """Already-scored issues should not be re-scored if unchanged."""
    count = await score_all_dirty()
    assert count == 0  # Both issues in seeded_db already have features
