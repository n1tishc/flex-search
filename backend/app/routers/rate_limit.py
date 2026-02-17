from fastapi import APIRouter

from app.services.github_client import github_client

router = APIRouter()


@router.get("/rate-limit")
async def rate_limit() -> dict:
    try:
        data = await github_client.get_rate_limit()
        core = data.get("resources", {}).get("core", {})
        search = data.get("resources", {}).get("search", {})
        return {
            "core": {
                "remaining": core.get("remaining", -1),
                "limit": core.get("limit", -1),
                "reset": core.get("reset"),
            },
            "search": {
                "remaining": search.get("remaining", -1),
                "limit": search.get("limit", -1),
                "reset": search.get("reset"),
            },
            "tracked": github_client.rate_limit.to_dict(),
        }
    except Exception as e:
        return {"error": str(e), "tracked": github_client.rate_limit.to_dict()}
