"""Branch naming for GitLab Issue workflow."""

from __future__ import annotations

import re

from control_panel.config import DiscordBotSettings
from control_panel.db.store import GenerationJob

_BRANCH_SLUG_RE = re.compile(r"[^a-zA-Z0-9._/-]+")


def resolve_issue_branch_template(settings: DiscordBotSettings) -> str:
    """Return the configured Git branch template for GitLab Issue jobs."""
    from_gitlab = settings.yaml.gitlab.issue_branch_template.strip()
    if from_gitlab:
        return from_gitlab
    return settings.yaml.gitlab_workflow.issue_branch_template


def _branch_token(value: str, *, fallback: str) -> str:
    cleaned = _BRANCH_SLUG_RE.sub("-", value.strip()).strip("-")
    return cleaned or fallback


def issue_branch_name(
    settings: DiscordBotSettings,
    *,
    issue_iid: int,
    feature_slug: str = "",
    job_id: str = "",
    template: str | None = None,
) -> str:
    """Return the Git branch name for one GitLab issue."""
    pattern = template or resolve_issue_branch_template(settings)
    return pattern.format(
        issue_iid=issue_iid,
        feature_slug=_branch_token(feature_slug, fallback="screen"),
        job_id=job_id,
    )


def resolve_issue_branch_name(
    settings: DiscordBotSettings,
    job: GenerationJob,
) -> str:
    """Resolve the issue branch name from current job metadata and YAML template."""
    issue_iid = job.gitlab_issue_iid or job.issue_number or 0
    if issue_iid <= 0:
        return job.publish_branch or job.gitlab_source_branch or ""
    return issue_branch_name(
        settings,
        issue_iid=issue_iid,
        feature_slug=job.feature_slug or "",
        job_id=job.id,
    )


def branch_tree_url(project_web_url: str, branch: str) -> str:
    """Return GitLab tree URL for a branch."""
    base = project_web_url.rstrip("/")
    from urllib.parse import quote

    return f"{base}/-/tree/{quote(branch, safe='')}"
