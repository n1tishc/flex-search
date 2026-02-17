from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()

_job_status: dict[str, dict] = {}


class JobStatus(BaseModel):
    name: str
    status: str  # "running", "completed", "failed"
    started_at: str | None = None
    completed_at: str | None = None
    result: dict | None = None
    error: str | None = None


async def _run_sync() -> None:
    _job_status["sync"] = {
        "name": "sync",
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        from app.services.ingestion_service import IngestionService
        svc = IngestionService()
        stats = await svc.run_full_sync()
        _job_status["sync"].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": stats,
        })
    except Exception as e:
        _job_status["sync"].update({
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        })


async def _run_score() -> None:
    _job_status["score"] = {
        "name": "score",
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        from app.services.feature_service import score_all_dirty
        count = await score_all_dirty()
        _job_status["score"].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": {"scored": count},
        })
    except Exception as e:
        _job_status["score"].update({
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        })


@router.post("/jobs/sync")
async def trigger_sync(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(_run_sync)
    return {"message": "Sync job started"}


@router.post("/jobs/score")
async def trigger_score(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(_run_score)
    return {"message": "Score job started"}


@router.get("/jobs/status/{name}", response_model=JobStatus)
async def job_status(name: str) -> JobStatus:
    info = _job_status.get(name)
    if info is None:
        return JobStatus(name=name, status="unknown")
    return JobStatus(**info)
