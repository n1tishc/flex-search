from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    language: str | None = None
    state: str | None = None  # "open" | "closed"
    labels: list[str] | None = None
    sort_by: str = "fixability"  # "fixability" | "created" | "updated" | "comments"
    page: int = 1
    per_page: int = 30
    enrich_top_n: int | None = None


class FixabilityBreakdown(BaseModel):
    repo_health: float = 0.0
    issue_signals: float = 0.0
    code_context: float = 0.0


class FixabilityResult(BaseModel):
    score: float = 0.0
    grade: str = "F"
    breakdown: FixabilityBreakdown = Field(default_factory=FixabilityBreakdown)
    enriched: bool = False


class RepoSummary(BaseModel):
    full_name: str
    stars: int = 0
    open_issues: int = 0
    language: str | None = None
    pushed_at: str | None = None
    archived: bool = False


class IssueResult(BaseModel):
    number: int
    title: str
    html_url: str
    state: str
    created_at: str
    updated_at: str
    comments: int = 0
    labels: list[str] = Field(default_factory=list)
    user: str = ""
    body_snippet: str = ""
    repo_full_name: str = ""


class ScoredIssue(BaseModel):
    issue: IssueResult
    repo_summary: RepoSummary | None = None
    fixability: FixabilityResult = Field(default_factory=FixabilityResult)


class RateLimitInfo(BaseModel):
    remaining: int = -1
    limit: int = -1
    reset_at: str | None = None


class SearchResponse(BaseModel):
    total_count: int = 0
    items: list[ScoredIssue] = Field(default_factory=list)
    rate_limit: RateLimitInfo = Field(default_factory=RateLimitInfo)


class IssueDetailResponse(BaseModel):
    issue: IssueResult
    repo_summary: RepoSummary | None = None
    fixability: FixabilityResult = Field(default_factory=FixabilityResult)
    linked_prs: list[dict] = Field(default_factory=list)
    similar_closed: list[dict] = Field(default_factory=list)
    timeline_events: list[dict] = Field(default_factory=list)


class JobStatus(BaseModel):
    name: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    result: dict | None = None
    error: str | None = None
