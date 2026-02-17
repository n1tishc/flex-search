from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepoRow:
    repo_id: int = 0
    full_name: str = ""
    owner: str = ""
    name: str = ""
    stars: int = 0
    forks: int = 0
    open_issues_count: int = 0
    language: str | None = None
    pushed_at: str | None = None
    updated_at: str | None = None
    archived: bool = False
    last_synced_at: str | None = None


@dataclass
class IssueRow:
    issue_id: int = 0
    repo_id: int = 0
    number: int = 0
    title: str = ""
    body: str = ""
    state: str = "open"
    user_login: str = ""
    labels: list[str] = field(default_factory=list)
    comments_count: int = 0
    html_url: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    closed_at: str | None = None


@dataclass
class IssueFeatures:
    issue_id: int = 0
    fixability_score: float = 0.0
    grade: str = "F"
    reasons: list[str] = field(default_factory=list)
    features: dict = field(default_factory=dict)
    computed_at: str | None = None
