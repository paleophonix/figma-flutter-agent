"""Public REST API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    """Body for ``POST /v1/jobs``."""

    figma_url: str = Field(min_length=8)
    repo_key: str | None = None
    mode: str = Field(default="new", pattern="^(new|existing)$")
    target_file: str | None = None


class JobResponse(BaseModel):
    """Public job view."""

    job_id: str
    status: str
    origin: str
    principal: str | None = None
    figma_url: str
    feature_slug: str | None = None
    repo_key: str | None = None
    target_mode: str | None = None
    target_file_path: str | None = None
    fixed_preview_url: str | None = None
    adaptive_preview_url: str | None = None
    artifact_zip_path: str | None = None
    publish_pr_url: str | None = None
    issue_url: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class CreateJobResponse(BaseModel):
    """Accepted job creation response."""

    job_id: str
    status: str


class JobListResponse(BaseModel):
    """Paginated job list."""

    items: list[JobResponse]
    limit: int
    offset: int


class CreateRepairJobRequest(BaseModel):
    """Body for ``POST /v1/repair-jobs``."""

    generation_job_id: str | None = None
    gitlab_project_id: str | None = None
    gitlab_issue_iid: int | None = None


class RepairJobResponse(BaseModel):
    """Public repair job view."""

    job_id: str
    status: str
    stage: str | None = None
    origin: str
    principal: str | None = None
    parent_generation_job_id: str | None = None
    feature_slug: str | None = None
    gitlab_mr_url: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class CreateRepairJobResponse(BaseModel):
    """Accepted repair job creation response."""

    job_id: str
    status: str
    queued_behind: str | None = None


class RepairJobListResponse(BaseModel):
    """Paginated repair job list."""

    items: list[RepairJobResponse]
    limit: int
    offset: int
