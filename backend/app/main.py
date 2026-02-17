from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import init_db, close_db
from app.routers import search, issue_detail, rate_limit, jobs
from app.services.github_client import github_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()
    await github_client.close()


app = FastAPI(title="GitHub Fixability Search", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api")
app.include_router(issue_detail.router, prefix="/api")
app.include_router(rate_limit.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
