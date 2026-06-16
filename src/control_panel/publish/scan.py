"""Scan remote repositories for screen file candidates."""

from __future__ import annotations

from control_panel.config import DiscordBotSettings
from control_panel.config.models import GitProvider, RepoConfig
from control_panel.services.github import GitHubClient
from control_panel.services.gitlab import GitLabClient


async def list_screen_candidates(
    settings: DiscordBotSettings,
    repo: RepoConfig,
) -> list[str]:
    """List Dart screen paths from the configured remote repository."""
    if repo.provider == GitProvider.GITHUB:
        client = GitHubClient(
            token=settings.github_token.get_secret_value(),
            repo=repo.github_repo or repo.remote,
        )
        return await client.list_dart_files(lib_root=repo.lib_root)
    project_id = repo.gitlab_project_id or settings.yaml.gitlab.app_project_id
    gitlab = GitLabClient(
        base_url=settings.yaml.gitlab.base_url,
        token=settings.gitlab_private_token.get_secret_value(),
    )
    return await gitlab.list_dart_files(project_id=project_id, lib_root=repo.lib_root)
