CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    figma_url TEXT NOT NULL,
    discord_user_id INTEGER NOT NULL,
    discord_channel_id INTEGER NOT NULL,
    discord_message_id INTEGER,
    review_message_id INTEGER,
    project_dir TEXT NOT NULL,
    feature_slug TEXT,
    status TEXT NOT NULL,
    fixed_preview_url TEXT,
    adaptive_preview_url TEXT,
    preview_token_hash TEXT,
    artifact_zip_path TEXT,
    artifact_repo_commit_url TEXT,
    gitlab_app_project_id TEXT,
    gitlab_issue_iid INTEGER,
    gitlab_issue_url TEXT,
    gitlab_mr_iid INTEGER,
    gitlab_mr_url TEXT,
    gitlab_source_branch TEXT,
    feedback_quality TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_generation_jobs_status ON generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_discord_user ON generation_jobs(discord_user_id);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_issue ON generation_jobs(gitlab_app_project_id, gitlab_issue_iid);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_mr ON generation_jobs(gitlab_app_project_id, gitlab_mr_iid);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_branch ON generation_jobs(gitlab_source_branch);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    discord_user_id INTEGER,
    action TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_events_job ON audit_events(job_id);
