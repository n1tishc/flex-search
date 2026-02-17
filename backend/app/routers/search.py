from fastapi import APIRouter

from app.models.schemas import SearchRequest, SearchResponse
from app.services.search_service import search_issues

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    return await search_issues(req)
