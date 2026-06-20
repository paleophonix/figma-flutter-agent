"""Branch naming for GitLab Issue workflow."""

from __future__ import annotations

from control_panel.config import DiscordBotSettings


def issue_branch_name(
    settings: DiscordBotSettings,
    *,
    issue_iid: int,
    feature_slug: str = "",
    job_id: str = "",
) -> str:
    """Return the Git branch name for one GitLab issue."""
    template = settings.yaml.gitlab_workflow.issue_branch_template
    return template.format(
        issue_iid=issue_iid,
        feature_slug=feature_slug or "screen",
        job_id=job_id,
    )


def branch_tree_url(project_web_url: str, branch: str) -> str:
    """Return GitLab tree URL for a branch."""
    base = project_web_url.rstrip("/")
    from urllib.parse import quote

    return f"{base}/-/tree/{quote(branch, safe='')}"
