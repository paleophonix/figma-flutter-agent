"""Resolve GitLab project metadata for Issue workflow jobs."""

from __future__ import annotations

from dataclasses import dataclass

from control_panel.config import DiscordBotSettings
from control_panel.config.models import GitProvider, RepoConfig
from control_panel.services.gitlab import GitLabClient


@dataclass(frozen=True)
class IssueProjectContext:
    """GitLab project backing one Issue."""

    project_id: str
    path_with_namespace: str
    web_url: str
    clone_url: str
    default_branch: str


def _gitlab_client(settings: DiscordBotSettings) -> GitLabClient:
    return GitLabClient(
        base_url=settings.yaml.gitlab.base_url,
        token=settings.gitlab_private_token.get_secret_value(),
    )


async def resolve_issue_project(
    settings: DiscordBotSettings,
    project_id: str,
) -> IssueProjectContext:
    """Load clone and web metadata for the Issue's GitLab project."""
    gitlab = _gitlab_client(settings)
    project = await gitlab.get_project(project_id)
    path = str(project.get("path_with_namespace") or project_id)
    web_url = str(project.get("web_url") or "").rstrip("/")
    http_url = str(project.get("http_url_to_repo") or "").strip()
    if not http_url:
        base = settings.yaml.gitlab.base_url.rstrip("/")
        http_url = f"{base}/{path}.git"
    default_branch = str(project.get("default_branch") or settings.yaml.gitlab.target_branch or "main")
    return IssueProjectContext(
        project_id=str(project.get("id") or project_id),
        path_with_namespace=path,
        web_url=web_url,
        clone_url=http_url,
        default_branch=default_branch,
    )


def issue_repo_config(context: IssueProjectContext) -> RepoConfig:
    """Build publish ``RepoConfig`` from Issue project context."""
    return RepoConfig(
        provider=GitProvider.GITLAB,
        remote=context.path_with_namespace,
        target_branch=context.default_branch,
        gitlab_project_id=context.project_id,
        bot_push=True,
    )


def issue_sandbox_dir(
    settings: DiscordBotSettings,
    *,
    project_id: str,
    issue_iid: int,
) -> str:
    """Return workspace sandbox path for one GitLab issue."""
    root = settings.yaml.projects.workspace_root.expanduser().resolve()
    return (root / "gitlab" / str(project_id) / str(issue_iid)).as_posix()
