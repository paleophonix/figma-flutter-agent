"""Post GitLab Issue comments for workflow lifecycle events."""

from __future__ import annotations

from control_panel.config import DiscordBotSettings
from control_panel.gitlab_workflow.branch import resolve_issue_branch_name
from control_panel.db.store import GenerationJob
from control_panel.services.gitlab import GitLabClient


def _gitlab(settings: DiscordBotSettings) -> GitLabClient:
    return GitLabClient(
        base_url=settings.yaml.gitlab.base_url,
        token=settings.gitlab_private_token.get_secret_value(),
    )


async def post_issue_comment(
    settings: DiscordBotSettings,
    *,
    project_id: str,
    issue_iid: int,
    body: str,
) -> None:
    """Post a note on a GitLab issue when credentials are configured."""
    token = settings.gitlab_private_token.get_secret_value().strip()
    if not token or not project_id or issue_iid <= 0:
        return
    await _gitlab(settings).create_issue_note(
        project_id=project_id,
        issue_iid=issue_iid,
        body=body,
    )


def build_preview_comment(
    *,
    fixed_preview_url: str,
    adaptive_preview_url: str,
    branch_url: str,
    branch_name: str,
    feature_slug: str,
) -> str:
    """Render the preview-ready issue comment."""
    lines = [
        f"**Preview ready** — `{feature_slug}`",
        "",
        f"- Fixed: {fixed_preview_url}",
        f"- Adaptive: {adaptive_preview_url}",
    ]
    if branch_url.strip():
        lines.append(f"- Code branch: {branch_url}")
    elif branch_name.strip():
        lines.append(
            f"- Code branch: `{branch_name}` (push failed — check token scopes: `api`, `write_repository`)"
        )
    else:
        lines.append("- Code branch: push failed — retry `/regen` or check control panel logs")
    return "\n".join(lines) + "\n"


async def post_preview_ready_comment(
    settings: DiscordBotSettings,
    job: GenerationJob,
    *,
    branch_url: str,
) -> None:
    """Notify the linked GitLab issue that preview and branch are ready."""
    project_id = job.gitlab_app_project_id or job.issue_project_ref or ""
    issue_iid = job.gitlab_issue_iid or job.issue_number or 0
    if not project_id or issue_iid <= 0:
        return
    body = build_preview_comment(
        fixed_preview_url=job.fixed_preview_url or "",
        adaptive_preview_url=job.adaptive_preview_url or "",
        branch_url=branch_url,
        branch_name=resolve_issue_branch_name(settings, job),
        feature_slug=job.feature_slug or "screen",
    )
    await post_issue_comment(
        settings,
        project_id=project_id,
        issue_iid=issue_iid,
        body=body,
    )


async def post_failure_comment(
    settings: DiscordBotSettings,
    job: GenerationJob,
    *,
    message: str,
) -> None:
    """Post a pipeline failure note on the linked GitLab issue."""
    project_id = job.gitlab_app_project_id or job.issue_project_ref or ""
    issue_iid = job.gitlab_issue_iid or job.issue_number or 0
    if not project_id or issue_iid <= 0:
        return
    await post_issue_comment(
        settings,
        project_id=project_id,
        issue_iid=issue_iid,
        body=f"**Generation failed**\n\n{message[:3500]}",
    )


async def post_mr_ready_comment(
    settings: DiscordBotSettings,
    job: GenerationJob,
    *,
    mr_url: str,
) -> None:
    """Post merge request link on the linked GitLab issue."""
    project_id = job.gitlab_app_project_id or job.issue_project_ref or ""
    issue_iid = job.gitlab_issue_iid or job.issue_number or 0
    if not project_id or issue_iid <= 0:
        return
    await post_issue_comment(
        settings,
        project_id=project_id,
        issue_iid=issue_iid,
        body=f"**Merge request ready:** {mr_url}",
    )


async def post_generation_started_comment(
    settings: DiscordBotSettings,
    job: GenerationJob,
) -> None:
    """Notify the linked GitLab issue that generation was queued."""
    project_id = job.gitlab_app_project_id or job.issue_project_ref or ""
    issue_iid = job.gitlab_issue_iid or job.issue_number or 0
    if not project_id or issue_iid <= 0:
        return
    branch = resolve_issue_branch_name(settings, job) or f"figma/issue-{issue_iid}"
    body = (
        "**Generation started** — Figma frame is being compiled to Flutter.\n\n"
        f"- Branch: `{branch}`\n"
        f"- Frame: {job.figma_url}\n"
    )
    await post_issue_comment(
        settings,
        project_id=project_id,
        issue_iid=issue_iid,
        body=body,
    )


async def post_regen_ack_comment(
    settings: DiscordBotSettings,
    *,
    project_id: str,
    issue_iid: int,
) -> None:
    """Acknowledge ``/regen`` or regeneration enqueue."""
    await post_issue_comment(
        settings,
        project_id=project_id,
        issue_iid=issue_iid,
        body="**Regeneration queued** — fresh Dart will be pushed to the issue branch.",
    )


async def post_bug_ack_comment(
    settings: DiscordBotSettings,
    *,
    project_id: str,
    issue_iid: int,
) -> None:
    """Acknowledge ``/bug`` repair enqueue."""
    await post_issue_comment(
        settings,
        project_id=project_id,
        issue_iid=issue_iid,
        body="**Repair queued** — assignee updated; a new preview will follow.",
    )
