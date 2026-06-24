"""Push generated sandbox output to the GitLab issue branch."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from control_panel.config import DiscordBotSettings
from control_panel.db.store import GenerationJob
from control_panel.gitlab_workflow.branch import branch_tree_url, resolve_issue_branch_name
from control_panel.gitlab_workflow.project import issue_repo_config, resolve_issue_project
from control_panel.publish.bundle import collect_repo_publish_files
from control_panel.publish.checkout import ensure_shallow_clone, repo_cache_dir
from control_panel.publish.migrate import migrate_sandbox_to_repo
from control_panel.services.gitlab import GitLabClient
from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.observability.posthog_business import (
    AGENT_COMMITTED_CHANGE,
    capture_business_event,
    infer_change_kind,
    resolve_distinct_id,
)


async def push_issue_branch(
    settings: DiscordBotSettings,
    job: GenerationJob,
) -> str:
    """Migrate sandbox files and commit them to the issue branch.

    Args:
        settings: Control panel settings.
        job: Generation job with GitLab linkage and sandbox path.

    Returns:
        GitLab tree URL for the pushed branch.

    Raises:
        FigmaFlutterError: When project linkage or generated files are missing.
    """
    project_id = job.gitlab_app_project_id or job.issue_project_ref or ""
    if not project_id:
        raise FigmaFlutterError("GitLab project id missing on generation job")
    branch = resolve_issue_branch_name(settings, job)
    if not branch:
        raise FigmaFlutterError("Issue branch name missing on generation job")

    context = await resolve_issue_project(settings, project_id)
    repo = issue_repo_config(context)
    repo_key = job.repo_key or project_id
    cache_root = agent_repo_root() / ".control-panel" / "cache" / "repos"
    repo_dir = ensure_shallow_clone(
        remote_url=context.clone_url,
        cache_dir=repo_cache_dir(cache_root, repo_key),
        branch=repo.target_branch,
        git_token=settings.gitlab_private_token.get_secret_value(),
    )
    sandbox_dir = Path(job.project_dir)
    migrated = migrate_sandbox_to_repo(
        sandbox_dir=sandbox_dir,
        repo_dir=repo_dir,
        job=job,
        custom_code_policy=settings.yaml.publish.custom_code_policy,
        include_debug_artifacts=settings.yaml.gitlab_workflow.commit_debug_artifacts,
    )
    files = collect_repo_publish_files(repo_dir, migrated)
    if not files:
        raise FigmaFlutterError("No generated files found to push to issue branch")

    feature_slug = job.feature_slug or job.id[:8]
    commit_message = f"feat: generated layout for {feature_slug}"
    gitlab = GitLabClient(
        base_url=settings.yaml.gitlab.base_url,
        token=settings.gitlab_private_token.get_secret_value(),
    )
    await gitlab.commit_files(
        project_id=project_id,
        branch=branch,
        commit_message=commit_message,
        files=files,
        start_branch=repo.target_branch,
    )
    capture_business_event(
        settings=settings,
        event=AGENT_COMMITTED_CHANGE,
        distinct_id=resolve_distinct_id(job_id=job.id, principal=job.principal),
        properties={
            "job_id": job.id,
            "branch": branch,
            "change_kind": infer_change_kind(commit_message=commit_message, branch=branch),
            "origin": job.origin.value,
        },
    )
    tree_url = branch_tree_url(context.web_url, branch)
    logger.info("Pushed issue branch {} for job {}", branch, job.id)
    return tree_url
