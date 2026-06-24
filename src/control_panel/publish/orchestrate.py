"""Publish orchestration entrypoint."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from control_panel.config import DiscordBotSettings
from control_panel.config.models import GitProvider, PrStrategy
from control_panel.db import JobOrigin
from control_panel.db.store import GenerationJob, JobStore, job_marker
from control_panel.publish.bundle import collect_repo_publish_files
from control_panel.publish.checkout import ensure_shallow_clone, repo_cache_dir
from control_panel.publish.migrate import migrate_sandbox_to_repo
from control_panel.services.github import GitHubClient
from control_panel.services.gitlab import GitLabClient
from control_panel.services.projects import (
    resolve_active_repo_key,
    resolve_repo_config,
)
from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.observability.posthog_business import (
    AGENT_COMMITTED_CHANGE,
    capture_business_event,
    infer_change_kind,
    resolve_distinct_id,
)


@dataclass(frozen=True)
class PublishResult:
    """Outcome of a publish run."""

    branch: str
    pr_url: str
    pr_number: int | None


def _remote_clone_url(settings: DiscordBotSettings, repo_key: str) -> str:
    repo = resolve_repo_config(settings, repo_key)
    if repo.provider == GitProvider.GITHUB:
        slug = repo.github_repo or repo.remote
        return f"https://github.com/{slug}.git"
    project = repo.gitlab_project_id or settings.yaml.gitlab.app_project_id
    if project.isdigit():
        return f"{settings.yaml.gitlab.base_url}/{project}.git"
    return f"{settings.yaml.gitlab.base_url}/{repo.remote}.git"


async def _resolve_publish_target(
    settings: DiscordBotSettings,
    store: JobStore,
    job: GenerationJob,
) -> tuple[str, GitProvider, str, str, str]:
    """Return repo_key, provider, clone URL, project id, target branch."""
    if job.origin == JobOrigin.GITLAB:
        from control_panel.gitlab_workflow.project import issue_repo_config, resolve_issue_project

        project_id = str(
            job.gitlab_app_project_id or job.issue_project_ref or job.repo_key or "",
        )
        if not project_id:
            raise FigmaFlutterError("GitLab project id missing on generation job")
        context = await resolve_issue_project(settings, project_id)
        repo = issue_repo_config(context)
        return project_id, repo.provider, context.clone_url, project_id, repo.target_branch

    repo_key = job.repo_key or await resolve_active_repo_key(settings, store, job.discord_user_id)
    repo = resolve_repo_config(settings, repo_key)
    project_id = repo.gitlab_project_id or settings.yaml.gitlab.app_project_id
    return repo_key, repo.provider, _remote_clone_url(settings, repo_key), project_id, repo.target_branch


async def run_publish_for_job(
    *,
    settings: DiscordBotSettings,
    store: JobStore,
    job: GenerationJob,
) -> PublishResult:
    """Migrate sandbox output and open or update a pull request."""
    repo_key, provider, clone_url, project_id, target_branch = await _resolve_publish_target(
        settings,
        store,
        job,
    )
    repo = resolve_repo_config(settings, repo_key) if job.origin != JobOrigin.GITLAB else None
    sandbox_dir = Path(job.project_dir)
    cache_root = agent_repo_root() / ".control-panel" / "cache" / "repos"
    repo_dir = ensure_shallow_clone(
        remote_url=clone_url,
        cache_dir=repo_cache_dir(cache_root, repo_key),
        branch=target_branch,
        git_token=(
            settings.gitlab_private_token.get_secret_value()
            if provider == GitProvider.GITLAB
            else settings.github_token.get_secret_value()
        ),
    )
    migrated = migrate_sandbox_to_repo(
        sandbox_dir=sandbox_dir,
        repo_dir=repo_dir,
        job=job,
        custom_code_policy=settings.yaml.publish.custom_code_policy,
    )
    files = collect_repo_publish_files(repo_dir, migrated)
    if not files:
        raise FigmaFlutterError("No generated files found to publish.")

    feature_slug = job.feature_slug or job.id[:8]
    strategy = settings.yaml.publish.pr_strategy
    if strategy == PrStrategy.BRANCH_MR:
        strategy = PrStrategy.NEW_PER_JOB
    branch = settings.yaml.publish.source_branch_template.format(
        job_id=job.id,
        feature_slug=feature_slug,
    )
    if job.origin == JobOrigin.GITLAB and job.publish_branch:
        branch = job.publish_branch
        strategy = PrStrategy.UPDATE_OPEN
    elif strategy == PrStrategy.UPDATE_OPEN and job.target_file_path:
        existing = await store.find_open_publish_job(
            repo_key=repo_key,
            target_file_path=job.target_file_path,
        )
        if existing and existing.publish_branch:
            branch = existing.publish_branch

    commit_message = f"feat: generated layout for {feature_slug}"
    description = (
        f"{job_marker(job.id)}\n\n"
        f"Figma: {job.figma_url}\n"
        f"Fixed preview: {job.fixed_preview_url}\n"
        f"Adaptive preview: {job.adaptive_preview_url}\n"
    )

    def _record_agent_commit(*, branch: str) -> None:
        capture_business_event(
            settings=settings,
            event=AGENT_COMMITTED_CHANGE,
            distinct_id=resolve_distinct_id(
                principal=job.principal,
                discord_user_id=job.discord_user_id,
                job_id=job.id,
            ),
            properties={
                "job_id": job.id,
                "branch": branch,
                "change_kind": infer_change_kind(commit_message=commit_message, branch=branch),
                "origin": job.origin.value,
            },
        )

    if provider == GitProvider.GITHUB:
        if repo is None:
            raise FigmaFlutterError("GitHub publish requires repository config")
        github = GitHubClient(
            token=settings.github_token.get_secret_value(),
            repo=repo.github_repo or repo.remote,
        )
        if strategy == PrStrategy.PUSH_MAIN:
            await github.commit_files(
                branch=target_branch,
                commit_message=commit_message,
                files=files,
            )
            _record_agent_commit(branch=target_branch)
            return PublishResult(branch=target_branch, pr_url=f"https://github.com/{repo.remote}/tree/{target_branch}", pr_number=None)
        await github.commit_files(
            branch=branch,
            commit_message=commit_message,
            files=files,
            start_branch=target_branch,
        )
        _record_agent_commit(branch=branch)
        open_pr = await github.find_open_pull_request(branch=branch, target_branch=target_branch)
        if open_pr is None:
            open_pr = await github.create_pull_request(
                source_branch=branch,
                target_branch=target_branch,
                title=f"Generated layout: {feature_slug}",
                description=description,
            )
        return PublishResult(
            branch=branch,
            pr_url=str(open_pr.get("html_url") or ""),
            pr_number=int(open_pr.get("number") or 0),
        )

    gitlab = GitLabClient(
        base_url=settings.yaml.gitlab.base_url,
        token=settings.gitlab_private_token.get_secret_value(),
    )
    if strategy == PrStrategy.PUSH_MAIN:
        commit = await gitlab.commit_files(
            project_id=project_id,
            branch=target_branch,
            commit_message=commit_message,
            files=files,
        )
        _record_agent_commit(branch=target_branch)
        return PublishResult(
            branch=target_branch,
            pr_url=str(commit.get("web_url") or ""),
            pr_number=None,
        )
    await gitlab.commit_files(
        project_id=project_id,
        branch=branch,
        commit_message=commit_message,
        files=files,
        start_branch=target_branch,
    )
    _record_agent_commit(branch=branch)
    open_mr = await gitlab.find_open_merge_request(
        project_id=project_id,
        source_branch=branch,
        target_branch=target_branch,
    )
    if open_mr is None:
        from control_panel.services.projects import resolve_gitlab_username

        initiator = resolve_gitlab_username(settings.yaml, job.discord_user_id)
        reviewers = [
            name
            for name in (initiator, settings.yaml.publish.boss_reviewer_username)
            if name
        ]
        open_mr = await gitlab.create_merge_request(
            project_id=project_id,
            source_branch=branch,
            target_branch=target_branch,
            title=f"Generated layout: {feature_slug}",
            description=description,
            assignee_username=settings.yaml.publish.assignee_username,
            reviewer_usernames=reviewers,
        )
    return PublishResult(
        branch=branch,
        pr_url=str(open_mr.get("web_url") or ""),
        pr_number=int(open_mr.get("iid") or 0),
    )
