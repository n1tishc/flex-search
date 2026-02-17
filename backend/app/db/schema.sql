CREATE TABLE IF NOT EXISTS repos (
    repo_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL UNIQUE,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    stars INTEGER NOT NULL DEFAULT 0,
    forks INTEGER NOT NULL DEFAULT 0,
    open_issues_count INTEGER NOT NULL DEFAULT 0,
    language TEXT,
    pushed_at TEXT,
    updated_at TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    last_synced_at TEXT
);

CREATE TABLE IF NOT EXISTS issues (
    issue_id INTEGER PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(repo_id),
    number INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'open',
    user_login TEXT NOT NULL DEFAULT '',
    labels TEXT NOT NULL DEFAULT '[]',
    comments_count INTEGER NOT NULL DEFAULT 0,
    html_url TEXT NOT NULL DEFAULT '',
    created_at TEXT,
    updated_at TEXT,
    closed_at TEXT,
    UNIQUE(repo_id, number)
);

CREATE TABLE IF NOT EXISTS comments (
    comment_id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES issues(issue_id),
    body TEXT NOT NULL DEFAULT '',
    user_login TEXT NOT NULL DEFAULT '',
    author_association TEXT NOT NULL DEFAULT '',
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS issue_features (
    issue_id INTEGER PRIMARY KEY REFERENCES issues(issue_id),
    fixability_score REAL NOT NULL DEFAULT 0,
    grade TEXT NOT NULL DEFAULT 'F',
    reasons TEXT NOT NULL DEFAULT '[]',
    features TEXT NOT NULL DEFAULT '{}',
    computed_at TEXT
);

-- FTS5 virtual table for full-text search on issues
CREATE VIRTUAL TABLE IF NOT EXISTS issues_fts USING fts5(
    title,
    body,
    content='issues',
    content_rowid='issue_id'
);

-- Triggers to keep FTS in sync with issues table
CREATE TRIGGER IF NOT EXISTS issues_ai AFTER INSERT ON issues BEGIN
    INSERT INTO issues_fts(rowid, title, body) VALUES (new.issue_id, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS issues_ad AFTER DELETE ON issues BEGIN
    INSERT INTO issues_fts(issues_fts, rowid, title, body) VALUES ('delete', old.issue_id, old.title, old.body);
END;

CREATE TRIGGER IF NOT EXISTS issues_au AFTER UPDATE ON issues BEGIN
    INSERT INTO issues_fts(issues_fts, rowid, title, body) VALUES ('delete', old.issue_id, old.title, old.body);
    INSERT INTO issues_fts(rowid, title, body) VALUES (new.issue_id, new.title, new.body);
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_issues_repo_id ON issues(repo_id);
CREATE INDEX IF NOT EXISTS idx_issues_state ON issues(state);
CREATE INDEX IF NOT EXISTS idx_issues_updated_at ON issues(updated_at);
CREATE INDEX IF NOT EXISTS idx_comments_issue_id ON comments(issue_id);
CREATE INDEX IF NOT EXISTS idx_issue_features_score ON issue_features(fixability_score DESC);
