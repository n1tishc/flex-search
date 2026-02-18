# GitHub Fixability Search

A search engine that ranks GitHub issues by a **fixability score** — a composite metric reflecting issue quality, maintainer engagement, and historical fix patterns. Find issues that are most likely to accept contributions.

## Architecture

```
                         ┌─────────────────────┐
                         │   Streamlit App      │
                         │   (streamlit_app.py) │
                         └────────┬─────────────┘
                                  │ direct import
              ┌───────────────────┼───────────────────┐
              │                   │                   │
     ┌────────▼──────┐  ┌────────▼──────┐  ┌────────▼──────┐
     │  SQLite DB    │  │  TF-IDF Index │  │  Score Engine │
     │  (aiosqlite)  │  │  (sklearn)    │  │               │
     └────────┬──────┘  └───────────────┘  └───────────────┘
              │
     ┌────────▼──────────────┐
     │  GitHub REST API      │
     │  (ingestion via CLI)  │
     └───────────────────────┘
```

There are two interfaces:

1. **Streamlit App** — single-process UI that reads directly from SQLite and uses TF-IDF for search ranking
2. **FastAPI Backend** — REST API with FTS5-based search (used by the legacy React frontend)

Both share the same database and scoring logic.

## Tech Stack

| Layer       | Technology                                    |
| ----------- | --------------------------------------------- |
| UI          | Streamlit 1.42                                |
| Search      | TF-IDF (scikit-learn) + cosine similarity     |
| API         | FastAPI, httpx (async)                        |
| Database    | SQLite (WAL mode) via aiosqlite               |
| Scoring     | Custom additive scoring engine                |
| Ingestion   | GitHub REST API via httpx                     |
| Config      | pydantic-settings (.env)                      |
| Tests       | pytest + pytest-asyncio (19 tests)            |

## Project Structure

```
github-fixability-search/
├── backend/
│   ├── streamlit_app.py               # Streamlit UI (TF-IDF search)
│   ├── repos.csv                      # List of repos to ingest (owner/repo)
│   ├── requirements.txt
│   ├── data/
│   │   └── fixability.db              # SQLite database (created by CLI)
│   ├── app/
│   │   ├── main.py                    # FastAPI app, CORS, lifespan
│   │   ├── config.py                  # Settings via pydantic-settings (.env)
│   │   ├── cli.py                     # Typer CLI: sync, score, full
│   │   ├── routers/
│   │   │   ├── search.py             # POST /api/search
│   │   │   ├── issue_detail.py       # GET /api/issue/{owner}/{repo}/{number}
│   │   │   └── rate_limit.py         # GET /api/rate-limit
│   │   ├── services/
│   │   │   ├── github_client.py      # Async httpx client + rate limit tracking
│   │   │   ├── ingestion_service.py  # GitHub API → DB sync (repos, issues, comments)
│   │   │   ├── feature_service.py    # Text feature extraction + scoring
│   │   │   ├── score_engine.py       # Fixability breakdown computation
│   │   │   ├── search_service.py     # Orchestrates search → enrich → score → sort
│   │   │   ├── enrichment_service.py # Concurrent API calls (asyncio.gather)
│   │   │   └── cache.py             # TTLCache instances
│   │   ├── models/
│   │   │   ├── schemas.py           # Pydantic request/response models
│   │   │   ├── db_models.py         # Dataclasses for DB rows
│   │   │   └── github_types.py      # Dataclasses for enrichment data
│   │   ├── db/
│   │   │   ├── connection.py         # Async SQLite init/get/close
│   │   │   ├── queries.py           # All SQL queries (upsert, search, lookup)
│   │   │   └── schema.sql           # Table definitions, FTS5, triggers, indexes
│   │   └── utils/
│   │       └── text_analysis.py     # Regex heuristics for reproduction info
│   └── tests/
│       ├── conftest.py
│       ├── test_score_engine.py      # 9 tests
│       ├── test_search_service.py    # 3 tests
│       ├── test_db_queries.py        # 5 tests
│       └── test_feature_service.py   # 2 tests
├── frontend/                          # Legacy React SPA (Vite + TypeScript)
├── .env.example
├── .gitignore
└── CLAUDE.md
```

## Quick Start

### 1. Setup

```bash
cd backend
cp ../.env.example .env
# Edit .env and add your GitHub token:
#   GITHUB_TOKEN=ghp_...
pip install -r requirements.txt
```

### 2. Ingest Data

Edit `repos.csv` to list the repositories you want to index (one `owner/repo` per line):

```csv
facebook/react
pallets/flask
tiangolo/fastapi
psf/requests
microsoft/vscode
```

Then run the full pipeline (sync from GitHub + compute scores):

```bash
python -m app.cli full
```

This will:
- Fetch repo metadata, issues (up to 500 per repo), and comments from the GitHub API
- Compute fixability scores for all ingested issues
- Store everything in `data/fixability.db`

You can also run the steps individually:

```bash
python -m app.cli sync     # Fetch from GitHub only
python -m app.cli score    # Compute scores only
```

### 3. Run the Streamlit App

```bash
cd backend
streamlit run streamlit_app.py
# Opens at http://localhost:8501
```

### 4. Run the FastAPI Backend (alternative)

```bash
cd backend
uvicorn app.main:app --reload
# API at http://localhost:8000
```

### 5. Run Tests

```bash
cd backend
python -m pytest tests/ -v
# 19 tests passing
```

## How It Works

### Data Pipeline

```
repos.csv → GitHub API → SQLite DB → Feature Extraction → Fixability Scoring
```

1. **Ingestion** (`app/services/ingestion_service.py`): Reads `repos.csv`, fetches repo metadata, issues (all states, up to 5 pages of 100), and comments for each issue from the GitHub REST API.

2. **Feature Extraction** (`app/utils/text_analysis.py`): Analyzes issue bodies with regex heuristics to detect:
   - Steps to reproduce
   - Expected vs actual behavior
   - Stack traces
   - Code blocks
   - Environment details (Python/Node/OS versions)

3. **Scoring** (`app/services/feature_service.py`): Computes an additive fixability score (0-100) from extracted features.

### Fixability Score

**Base score:** 50 points

**Positive signals:**

| Signal                          | Points |
| ------------------------------- | ------ |
| Maintainer replied              | +10    |
| Steps to reproduce              | +8     |
| "good first issue" label        | +8     |
| "help wanted" label             | +6     |
| Expected vs actual              | +5     |
| Active discussion (3+ comments) | +5     |
| Stack trace                     | +4     |
| Environment details (2+)        | +4     |
| "bug" label                     | +3     |
| Code block                      | +3     |

**Negative signals:**

| Signal                    | Points |
| ------------------------- | ------ |
| wontfix/invalid/duplicate | -20    |
| blocked/waiting label     | -15    |
| Closed state              | -10    |
| Stale (180+ days)         | -8     |
| Aging (90+ days)          | -4     |

**Grades:** A (80+), B (60-79), C (40-59), D (20-39), F (<20)

### Fixability Breakdown

The overall score is decomposed into three buckets for display:

- **Repo Health** (35% weight): Issue state, maintainer engagement, comment activity
- **Issue Signals** (35% weight): Labels (good first issue, help wanted, bug), maintainer replies
- **Code Context** (30% weight): Steps to reproduce, expected/actual, stack traces, code blocks, environment details

### Search (Streamlit — TF-IDF)

The Streamlit app uses TF-IDF vectorization for search:

1. On startup, loads all issues from SQLite into memory
2. Builds a TF-IDF matrix over `title + body` (20k max features, bigrams, sublinear TF, English stop words removed)
3. On query, computes cosine similarity between query vector and all issue vectors
4. **Combined ranking:** `0.6 * cosine_similarity + 0.4 * fixability_score` — surfaces issues that are both relevant and fixable
5. Results filtered by optional language and state filters
6. Minimum similarity threshold of 0.01 filters out irrelevant results

### Search (FastAPI — FTS5)

The FastAPI backend uses SQLite FTS5 with BM25 ranking:

- Full-text search on issue title + body via `issues_fts` virtual table
- Kept in sync with triggers on INSERT/UPDATE/DELETE
- Reranking: `0.65 * BM25 + 0.35 * fixability_score`

## Database Schema

```sql
repos           -- Repository metadata (stars, forks, language, pushed_at, archived)
issues          -- Issue data (title, body, state, labels JSON, comments_count, html_url)
comments        -- Issue comments with user_login and author_association
issue_features  -- Pre-computed fixability scores, grades, reasons, and feature vectors
issues_fts      -- FTS5 virtual table for full-text search (title + body)
```

Key design decisions:
- **WAL mode** for concurrent reads during Streamlit serving
- **FTS5 triggers** keep the search index in sync automatically on INSERT/UPDATE/DELETE
- **JSON columns** for labels, reasons, and feature dicts
- **Unique constraint** on `(repo_id, number)` prevents duplicate issues
- **Upsert pattern** (`ON CONFLICT DO UPDATE`) for idempotent ingestion

## Configuration

All settings are loaded from environment variables or `.env` file:

| Variable                  | Default                  | Description                           |
| ------------------------- | ------------------------ | ------------------------------------- |
| `GITHUB_TOKEN`            | (empty)                  | GitHub PAT for API access             |
| `GITHUB_API_BASE`         | `https://api.github.com` | GitHub API base URL                   |
| `DB_PATH`                 | `data/fixability.db`     | SQLite database path                  |
| `REPOS_CSV_PATH`          | `repos.csv`              | Path to repo list CSV                 |
| `TEXT_SCORE_WEIGHT`       | `0.65`                   | BM25 weight in combined ranking       |
| `FIXABILITY_SCORE_WEIGHT` | `0.35`                   | Fixability weight in combined ranking  |
| `MAX_CONCURRENCY`         | `15`                     | Semaphore limit for parallel API calls |

## Rate Limits

Without a token: 60 core + 10 search requests/minute. With a token: 5,000 core + 30 search/minute.

The `RateLimitTracker` in `github_client.py` monitors remaining quota and exposes a budget mode:

| Mode         | Remaining | Behavior                                  |
| ------------ | --------- | ----------------------------------------- |
| **Full**     | >200      | Enrich top 10, all signals                |
| **Conserve** | 50-200    | Enrich top 3, skip contributors + similar |
| **Minimal**  | <50       | Lite scores only, no enrichment           |

## Streamlit UI Features

- **Search bar** with TF-IDF-powered fuzzy matching
- **Sidebar filters**: language dropdown (auto-populated from DB), issue state (open/closed)
- **Index stats**: total issues and repos displayed in sidebar
- **Result cards** showing:
  - State badge (green for open, red for closed)
  - Issue title as clickable link to GitHub
  - Metadata line: repo, issue number, age, author, comment count
  - Labels as styled badges
  - Body snippet (first 300 characters)
  - Star count and language
  - Fixability grade badge (color-coded A-F) with percentage
  - Expandable fixability breakdown with progress bars for each of the 3 buckets

## CLI Commands

```bash
python -m app.cli sync [--csv-path PATH]   # Sync repos/issues/comments from GitHub
python -m app.cli score                     # Compute fixability scores for unscored issues
python -m app.cli full [--csv-path PATH]    # Run sync + score in sequence
```

## Known Issue

The Streamlit app has a transitive import conflict: importing `app.services.score_engine` pulls in `app.services.feature_service` which imports `app.db.queries` (async code using `aiosqlite`). While the Streamlit app itself uses synchronous `sqlite3`, this import chain can trigger `RuntimeError: no current event loop` in some Python environments. The workaround is to inline the score computation logic directly in `streamlit_app.py` instead of importing from the `app` package.
