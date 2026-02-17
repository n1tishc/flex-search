import json
import pytest

from app.db import queries


@pytest.mark.asyncio
async def test_upsert_and_get_repo(db):
    await queries.upsert_repo(
        repo_id=1,
        full_name="owner/repo",
        owner="owner",
        name="repo",
        stars=100,
    )
    row = await queries.get_repo_by_name("owner", "repo")
    assert row is not None
    assert row["full_name"] == "owner/repo"
    assert row["stars"] == 100


@pytest.mark.asyncio
async def test_upsert_issue_and_search(db):
    await queries.upsert_repo(
        repo_id=1, full_name="owner/repo", owner="owner", name="repo"
    )
    await queries.upsert_issue(
        issue_id=101,
        repo_id=1,
        number=42,
        title="Memory leak in parser",
        body="There is a memory leak when parsing large files.",
        state="open",
        user_login="alice",
        labels=["bug"],
        comments_count=3,
        html_url="https://github.com/owner/repo/issues/42",
        created_at="2026-02-01T00:00:00Z",
        updated_at="2026-02-10T00:00:00Z",
    )

    rows, total = await queries.search_issues_fts("memory leak")
    assert total >= 1
    assert rows[0]["number"] == 42


@pytest.mark.asyncio
async def test_get_issue_by_repo_and_number(seeded_db):
    row = await queries.get_issue_by_repo_and_number("owner", "repo", 42)
    assert row is not None
    assert row["title"] == "TypeError when calling parse()"
    assert row["fixability_score"] == 76


@pytest.mark.asyncio
async def test_get_comments_for_issue(seeded_db):
    comments = await queries.get_comments_for_issue(101)
    assert len(comments) == 1
    assert comments[0]["author_association"] == "MEMBER"


@pytest.mark.asyncio
async def test_get_dirty_issues(db):
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
           VALUES (301, 1, 1, 'Dirty issue', 'Needs scoring', 'open', 'user1',
                   '[]', 0, 'https://github.com/test/repo/issues/1',
                   '2026-02-01T00:00:00Z', '2026-02-10T00:00:00Z')"""
    )
    await db.commit()

    dirty = await queries.get_dirty_issues()
    assert len(dirty) == 1
    assert dirty[0]["issue_id"] == 301
