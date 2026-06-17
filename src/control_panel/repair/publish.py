"""Publish repair worktree changes as a GitLab merge request."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from control_panel.config import DiscordBotSettings
from control_panel.db.repair_store import RepairJob
from control_panel.services.gitlab import GitLabClient
from figma_flutter_agent.errors import FigmaFlutterError


@dataclass(frozen=True)
class RepairPublishResult:
    """Outcome of repair MR publish."""

    branch: str
    mr_url: str
    mr_iid: int | None


def _changed_files(worktree: Path) -> dict[str, Path]:
    """Return relative path → absolute path for modified tracked files."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise FigmaFlutterError((result.stderr or result.stdout or "git status failed").strip())
    files: dict[str, Path] = {}
    for line in (result.stdout or "").splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if not path or path.startswith(".repair/"):
            continue
        file_path = worktree / path
        if file_path.is_file():
            files[path.replace("\\", "/")] = file_path
    return files


async def run_repair_publish(
    *,
    settings: DiscordBotSettings,
    job: RepairJob,
    worktree: Path,
) -> RepairPublishResult:
    """Commit worktree changes and open a GitLab MR (manual merge).

    Args:
        settings: Control plane settings.
        job: Repair job with GitLab linkage.
        worktree: Agent-repo worktree with applied fixes.

    Returns:
        RepairPublishResult with MR metadata.

    Raises:
        FigmaFlutterError: When no changes or GitLab API fails.
    """
    files = _changed_files(worktree)
    if not files:
        raise FigmaFlutterError("No repair changes to publish")
    project_id = (
        settings.yaml.repair.gitlab_project_id.strip()
        or settings.yaml.gitlab.app_project_id.strip()
    )
    if not project_id:
        raise FigmaFlutterError("repair.gitlab_project_id or gitlab.app_project_id required")
    target_branch = settings.yaml.gitlab.target_branch
    branch = f"repair/{job.id}"
    gitlab = GitLabClient(
        base_url=settings.yaml.gitlab.base_url,
        token=settings.gitlab_private_token.get_secret_value(),
    )
    commit_message = f"fix(compiler): auto-repair {job.id}"
    description = (
        f"Auto-repair job `{job.id}`\n\n"
        f"Parent generation job: `{job.parent_generation_job_id or 'n/a'}`\n"
        f"Feature: `{job.feature_slug or 'n/a'}`\n"
    )
    await gitlab.commit_files(
        project_id=project_id,
        branch=branch,
        commit_message=commit_message,
        files=files,
        start_branch=target_branch,
    )
    open_mr = await gitlab.find_open_merge_request(
        project_id=project_id,
        source_branch=branch,
        target_branch=target_branch,
    )
    if open_mr is None:
        open_mr = await gitlab.create_merge_request(
            project_id=project_id,
            source_branch=branch,
            target_branch=target_branch,
            title=f"Auto-repair: {job.feature_slug or job.id[:8]}",
            description=description,
            assignee_username=settings.yaml.publish.assignee_username,
            reviewer_usernames=[],
        )
    return RepairPublishResult(
        branch=branch,
        mr_url=str(open_mr.get("web_url") or ""),
        mr_iid=int(open_mr.get("iid") or 0) or None,
    )
