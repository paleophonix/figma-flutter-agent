"""GitLab coarse repair status and ticket comments."""

from __future__ import annotations

from control_panel.config import DiscordBotSettings
from control_panel.db.enums import RepairJobStatus
from control_panel.db.repair_store import RepairJob
from control_panel.services.gitlab import GitLabClient

STATUS_LABEL_PREFIX = "repair-status::"


def status_label(status: RepairJobStatus) -> str:
    """Map repair status to a GitLab label."""
    return f"{STATUS_LABEL_PREFIX}{status.value}"


def render_status_comment(status: RepairJobStatus, *, repair_job_id: str) -> str:
    """Render a short coarse-status note for GitLab."""
    return f"**Auto-repair `{repair_job_id}`:** `{status.value}`"


async def post_ticket_comment(
    settings: DiscordBotSettings,
    *,
    project_id: str,
    issue_iid: int,
    body: str,
) -> None:
    """Post the RepairTicket markdown as a new issue note."""
    token = settings.gitlab_private_token.get_secret_value().strip()
    if not token or not project_id or issue_iid <= 0:
        return
    gitlab = GitLabClient(base_url=settings.yaml.gitlab.base_url, token=token)
    await gitlab.create_issue_note_with_upload(
        project_id=project_id,
        issue_iid=issue_iid,
        body=body,
    )


async def post_status_comment(
    settings: DiscordBotSettings,
    job: RepairJob,
    status: RepairJobStatus,
) -> None:
    """Post coarse repair status to the linked GitLab issue."""
    project_id = job.gitlab_project_id or ""
    issue_iid = job.gitlab_issue_iid or 0
    if not project_id or issue_iid <= 0:
        return
    body = render_status_comment(status, repair_job_id=job.id)
    await post_ticket_comment(
        settings,
        project_id=project_id,
        issue_iid=issue_iid,
        body=body,
    )
