import pytest

from app.models.schemas import SearchRequest
from app.services.search_service import search_issues


@pytest.mark.asyncio
async def test_search_returns_results(seeded_db):
    req = SearchRequest(query="TypeError")
    resp = await search_issues(req)
    assert resp.total_count >= 1
    assert len(resp.items) >= 1
    item = resp.items[0]
    assert item.issue.number == 42
    assert item.fixability.score > 0
    assert item.fixability.grade in ("A", "B", "C", "D", "F")
    assert item.repo_summary is not None
    assert item.repo_summary.full_name == "owner/repo"


@pytest.mark.asyncio
async def test_search_no_results(seeded_db):
    req = SearchRequest(query="nonexistent_query_xyz")
    resp = await search_issues(req)
    assert resp.total_count == 0
    assert len(resp.items) == 0


@pytest.mark.asyncio
async def test_search_with_state_filter(seeded_db):
    req = SearchRequest(query="pointer", state="closed")
    resp = await search_issues(req)
    assert resp.total_count >= 1
    for item in resp.items:
        assert item.issue.state == "closed"
