from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite

from app.db.connection import get_db


async def upsert_repo(
    repo_id: int,
    full_name: str,
    owner: str,
    name: str,
    stars: int = 0,
    forks: int = 0,
    open_issues_count: int = 0,
    language: str | None = None,
    pushed_at: str | None = None,
    updated_at: str | None = None,
    archived: bool = False,
) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO repos (repo_id, full_name, owner, name, stars, forks,
                              open_issues_count, language, pushed_at, updated_at, archived, last_synced_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(repo_id) DO UPDATE SET
               full_name=excluded.full_name, owner=excluded.owner, name=excluded.name,
               stars=excluded.stars, forks=excluded.forks,
               open_issues_count=excluded.open_issues_count, language=excluded.language,
               pushed_at=excluded.pushed_at, updated_at=excluded.updated_at,
               archived=excluded.archived, last_synced_at=excluded.last_synced_at""",
        (repo_id, full_name, owner, name, stars, forks, open_issues_count,
         language, pushed_at, updated_at, int(archived),
         datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()


async def upsert_issue(
    issue_id: int,
    repo_id: int,
    number: int,
    title: str = "",
    body: str = "",
    state: str = "open",
    user_login: str = "",
    labels: list[str] | None = None,
    comments_count: int = 0,
    html_url: str = "",
    created_at: str | None = None,
    updated_at: str | None = None,
    closed_at: str | None = None,
) -> None:
    db = await get_db()
    labels_json = json.dumps(labels or [])
    await db.execute(
        """INSERT INTO issues (issue_id, repo_id, number, title, body, state,
                               user_login, labels, comments_count, html_url,
                               created_at, updated_at, closed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(issue_id) DO UPDATE SET
               title=excluded.title, body=excluded.body, state=excluded.state,
               user_login=excluded.user_login, labels=excluded.labels,
               comments_count=excluded.comments_count, html_url=excluded.html_url,
               updated_at=excluded.updated_at, closed_at=excluded.closed_at""",
        (issue_id, repo_id, number, title, body, state, user_login, labels_json,
         comments_count, html_url, created_at, updated_at, closed_at),
    )
    await db.commit()


async def upsert_comment(
    comment_id: int,
    issue_id: int,
    body: str = "",
    user_login: str = "",
    author_association: str = "",
    created_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO comments (comment_id, issue_id, body, user_login,
                                 author_association, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(comment_id) DO UPDATE SET
               body=excluded.body, user_login=excluded.user_login,
               author_association=excluded.author_association,
               updated_at=excluded.updated_at""",
        (comment_id, issue_id, body, user_login, author_association,
         created_at, updated_at),
    )
    await db.commit()


async def upsert_issue_features(
    issue_id: int,
    fixability_score: float,
    grade: str,
    reasons: list[str],
    features: dict,
) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO issue_features (issue_id, fixability_score, grade, reasons, features, computed_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(issue_id) DO UPDATE SET
               fixability_score=excluded.fixability_score, grade=excluded.grade,
               reasons=excluded.reasons, features=excluded.features,
               computed_at=excluded.computed_at""",
        (issue_id, fixability_score, grade, json.dumps(reasons),
         json.dumps(features), datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()


async def get_dirty_issues(limit: int = 500) -> list[aiosqlite.Row]:
    """Get issues that have no computed features or were updated after last scoring."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT i.issue_id, i.repo_id, i.number, i.title, i.body, i.state,
                  i.user_login, i.labels, i.comments_count, i.html_url,
                  i.created_at, i.updated_at, i.closed_at,
                  r.full_name AS repo_full_name, r.stars, r.language, r.pushed_at, r.archived
           FROM issues i
           JOIN repos r ON i.repo_id = r.repo_id
           LEFT JOIN issue_features f ON i.issue_id = f.issue_id
           WHERE f.issue_id IS NULL
              OR i.updated_at > f.computed_at
           LIMIT ?""",
        (limit,),
    )
    return await cursor.fetchall()


async def search_issues_fts(
    query: str,
    language: str | None = None,
    state: str | None = None,
    labels: list[str] | None = None,
    sort_by: str = "fixability",
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[aiosqlite.Row], int]:
    """Full-text search on issues with optional filters and reranking."""
    db = await get_db()

    where_clauses = ["issues_fts MATCH ?"]
    params: list = [query]

    if language:
        where_clauses.append("r.language = ?")
        params.append(language)
    if state:
        where_clauses.append("i.state = ?")
        params.append(state)
    if labels:
        for label in labels:
            where_clauses.append("i.labels LIKE ?")
            params.append(f'%"{label}"%')

    where = " AND ".join(where_clauses)

    # Count query
    count_sql = f"""
        SELECT COUNT(*) FROM issues_fts
        JOIN issues i ON issues_fts.rowid = i.issue_id
        JOIN repos r ON i.repo_id = r.repo_id
        LEFT JOIN issue_features f ON i.issue_id = f.issue_id
        WHERE {where}
    """
    cursor = await db.execute(count_sql, params)
    row = await cursor.fetchone()
    total_count = row[0] if row else 0

    # Result query with reranking
    if sort_by == "fixability":
        order = "COALESCE(f.fixability_score, 0) DESC"
    else:
        order = """(
            1.0 / (1.0 + ABS(bm25(issues_fts))) * 0.65
            + COALESCE(f.fixability_score, 0) / 100.0 * 0.35
        ) DESC"""

    results_sql = f"""
        SELECT i.issue_id, i.repo_id, i.number, i.title, i.body, i.state,
               i.user_login, i.labels, i.comments_count, i.html_url,
               i.created_at, i.updated_at, i.closed_at,
               r.full_name AS repo_full_name, r.stars, r.open_issues_count,
               r.language, r.pushed_at, r.archived,
               COALESCE(f.fixability_score, 0) AS fixability_score,
               COALESCE(f.grade, 'F') AS grade,
               COALESCE(f.reasons, '[]') AS reasons,
               COALESCE(f.features, '{{}}') AS features,
               bm25(issues_fts) AS bm25_score
        FROM issues_fts
        JOIN issues i ON issues_fts.rowid = i.issue_id
        JOIN repos r ON i.repo_id = r.repo_id
        LEFT JOIN issue_features f ON i.issue_id = f.issue_id
        WHERE {where}
        ORDER BY {order}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    cursor = await db.execute(results_sql, params)
    rows = await cursor.fetchall()
    return rows, total_count


async def get_issue_by_repo_and_number(
    owner: str, repo: str, number: int
) -> aiosqlite.Row | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT i.issue_id, i.repo_id, i.number, i.title, i.body, i.state,
                  i.user_login, i.labels, i.comments_count, i.html_url,
                  i.created_at, i.updated_at, i.closed_at,
                  r.full_name AS repo_full_name, r.stars, r.open_issues_count,
                  r.language, r.pushed_at, r.archived,
                  COALESCE(f.fixability_score, 0) AS fixability_score,
                  COALESCE(f.grade, 'F') AS grade,
                  COALESCE(f.reasons, '[]') AS reasons,
                  COALESCE(f.features, '{}') AS features
           FROM issues i
           JOIN repos r ON i.repo_id = r.repo_id
           LEFT JOIN issue_features f ON i.issue_id = f.issue_id
           WHERE r.owner = ? AND r.name = ? AND i.number = ?""",
        (owner, repo, number),
    )
    return await cursor.fetchone()


async def get_comments_for_issue(issue_id: int) -> list[aiosqlite.Row]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT comment_id, issue_id, body, user_login, author_association,
                  created_at, updated_at
           FROM comments WHERE issue_id = ? ORDER BY created_at""",
        (issue_id,),
    )
    return await cursor.fetchall()


async def get_repo_by_name(owner: str, name: str) -> aiosqlite.Row | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM repos WHERE owner = ? AND name = ?",
        (owner, name),
    )
    return await cursor.fetchone()


async def get_all_repos() -> list[aiosqlite.Row]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM repos")
    return await cursor.fetchall()
