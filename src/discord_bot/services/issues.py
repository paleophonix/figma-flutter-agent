"""Unified issue tracker facade for GitLab and GitHub."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from discord_bot.config import DiscordBotSettings
from discord_bot.config.models import GitProvider, RepoConfig
from discord_bot.db import FEEDBACK_LABELS, ISSUE_KIND_LABELS, IssueKind, Quality
from discord_bot.db.store import GenerationJob, job_marker
from discord_bot.runner.review import FeedbackReview
from discord_bot.services.github import GitHubClient
from discord_bot.services.gitlab import GitLabClient


@dataclass(frozen=True)
class CreatedIssue:
    """Created remote issue reference."""

    provider: str
    project_ref: str
    number: int
    url: str


def priority_labels(settings: DiscordBotSettings, quality: Quality) -> list[str]:
    """Return configured priority labels for a feedback quality rating."""
    configured = settings.yaml.feedback.priority_labels.get(quality.value, [])
    base = [
        "agent-feedback",
        FEEDBACK_LABELS[quality],
        ISSUE_KIND_LABELS[IssueKind.BUG],
        "generated-layout",
    ]
    return base + list(configured)


def feat_issue_labels() -> list[str]:
    """Return labels for accepted-layout feature tracker issues."""
    return [
        "agent-feedback",
        FEEDBACK_LABELS[Quality.GOOD],
        ISSUE_KIND_LABELS[IssueKind.FEAT],
        "generated-layout",
    ]


def resolve_app_project_ref(settings: DiscordBotSettings, repo: RepoConfig) -> str:
    """Return the tracker project reference for an app repository."""
    if repo.provider == GitProvider.GITHUB:
        return repo.github_repo or repo.remote
    return repo.gitlab_project_id or settings.yaml.gitlab.app_project_id


def resolve_artifacts_remote(settings: DiscordBotSettings) -> str:
    """Return artifacts repository remote, with legacy GitLab fallback."""
    remote = settings.yaml.artifacts.remote.strip()
    if remote:
        return remote
    return settings.yaml.gitlab.artifacts_project_id.strip()


def artifacts_provider(remote: str) -> GitProvider:
    """Infer provider from artifacts remote shape."""
    if remote.isdigit() or "/" not in remote:
        return GitProvider.GITLAB
    return GitProvider.GITHUB


def build_issue_description(
    *,
    job: GenerationJob,
    review: FeedbackReview,
    artifact_repo_url: str,
) -> str:
    """Compose issue body with marker, review, previews, and artifact links."""
    return (
        f"{job_marker(job.id)}\n\n"
        f"{review.body}\n\n"
        f"## Комментарий пользователя\n\n"
        f"{job.feedback_comment or '(нет)'}\n\n"
        f"## Превью\n"
        f"- Fixed: {job.fixed_preview_url}\n"
        f"- Adaptive: {job.adaptive_preview_url}\n\n"
        f"## Артефакты\n"
        f"- Repo: {artifact_repo_url or '(none)'}\n"
        f"- Zip: {job.artifact_zip_path or '(local)'}\n"
    )


class IssueService:
    """Create and close feedback issues across GitLab and GitHub."""

    def __init__(self, settings: DiscordBotSettings) -> None:
        self._settings = settings

    def _gitlab(self) -> GitLabClient:
        return GitLabClient(
            base_url=self._settings.yaml.gitlab.base_url,
            token=self._settings.gitlab_private_token.get_secret_value(),
        )

    def _github(self, repo: str) -> GitHubClient:
        return GitHubClient(
            token=self._settings.github_token.get_secret_value(),
            repo=repo,
        )

    async def create_feedback_issue(
        self,
        *,
        job: GenerationJob,
        repo: RepoConfig,
        review: FeedbackReview,
        quality: Quality,
        zip_path: Path | None,
        artifact_repo_url: str,
    ) -> CreatedIssue:
        """Open a feedback issue and attach the artifact zip when possible."""
        labels = priority_labels(self._settings, quality)
        description = build_issue_description(
            job=job,
            review=review,
            artifact_repo_url=artifact_repo_url,
        )
        assignee = self._settings.yaml.publish.assignee_username
        project_ref = resolve_app_project_ref(self._settings, repo)

        if repo.provider == GitProvider.GITHUB:
            slug = repo.github_repo or repo.remote
            client = self._github(slug)
            issue = await client.create_issue(
                title=review.title,
                body=description,
                labels=labels,
            )
            number = int(issue.get("number") or 0)
            url = str(issue.get("html_url") or "")
            if zip_path is not None and zip_path.is_file():
                await client.create_issue_comment(
                    issue_number=number,
                    body=f"Артефакты: {artifact_repo_url}\n\nZip: `{zip_path.name}`",
                )
            return CreatedIssue(
                provider=GitProvider.GITHUB.value,
                project_ref=slug,
                number=number,
                url=url,
            )

        gitlab = self._gitlab()
        issue = await gitlab.create_issue(
            project_id=project_ref,
            title=review.title,
            description=description,
            labels=labels,
            assignee_username=assignee,
        )
        iid = int(issue.get("iid") or 0)
        url = str(issue.get("web_url") or "")
        if zip_path is not None and zip_path.is_file():
            await gitlab.create_issue_note_with_upload(
                project_id=project_ref,
                issue_iid=iid,
                body="Артефактный bundle прикреплён.",
                upload_path=zip_path,
            )
        return CreatedIssue(
            provider=GitProvider.GITLAB.value,
            project_ref=project_ref,
            number=iid,
            url=url,
        )

    async def create_feat_issue(
        self,
        *,
        job: GenerationJob,
        repo: RepoConfig,
        mr_url: str,
        feature_slug: str,
    ) -> CreatedIssue:
        """Open a feature tracker issue linked to a published merge request."""
        labels = feat_issue_labels()
        description = (
            f"{job_marker(job.id)}\n\n"
            f"Figma: {job.figma_url}\n"
            f"Merge request: {mr_url}\n\n"
            f"## Превью\n"
            f"- Fixed: {job.fixed_preview_url}\n"
            f"- Adaptive: {job.adaptive_preview_url}\n"
        )
        title = f"feat: generated layout for {feature_slug}"
        assignee = self._settings.yaml.publish.assignee_username
        project_ref = resolve_app_project_ref(self._settings, repo)

        if repo.provider == GitProvider.GITHUB:
            slug = repo.github_repo or repo.remote
            issue = await self._github(slug).create_issue(
                title=title,
                body=description,
                labels=labels,
            )
            return CreatedIssue(
                provider=GitProvider.GITHUB.value,
                project_ref=slug,
                number=int(issue.get("number") or 0),
                url=str(issue.get("html_url") or ""),
            )

        issue = await self._gitlab().create_issue(
            project_id=project_ref,
            title=title,
            description=description,
            labels=labels,
            assignee_username=assignee,
        )
        return CreatedIssue(
            provider=GitProvider.GITLAB.value,
            project_ref=project_ref,
            number=int(issue.get("iid") or 0),
            url=str(issue.get("web_url") or ""),
        )

    async def close_issue(self, job: GenerationJob) -> None:
        """Close the remote issue linked to a job."""
        provider = job.issue_provider or "gitlab"
        project_ref = job.issue_project_ref or job.gitlab_app_project_id or ""
        number = job.issue_number or job.gitlab_issue_iid
        if not project_ref or number is None:
            msg = f"Job {job.id} has no linked issue"
            raise ValueError(msg)

        if provider == GitProvider.GITHUB.value:
            await self._github(project_ref).close_issue(issue_number=int(number))
            return
        await self._gitlab().close_issue(project_id=project_ref, issue_iid=int(number))

    async def fetch_last_issue_comment(self, job: GenerationJob) -> str | None:
        """Return the latest non-system issue note or comment body."""
        provider = job.issue_provider or "gitlab"
        project_ref = job.issue_project_ref or job.gitlab_app_project_id or ""
        number = job.issue_number or job.gitlab_issue_iid
        if not project_ref or number is None:
            return None

        if provider == GitProvider.GITHUB.value:
            comments = await self._github(project_ref).list_issue_comments(
                issue_number=int(number),
            )
            if not comments:
                return None
            return str(comments[-1].get("body") or "").strip() or None

        notes = await self._gitlab().list_issue_notes(
            project_id=project_ref,
            issue_iid=int(number),
        )
        for note in reversed(notes):
            if note.get("system"):
                continue
            body = str(note.get("body") or "").strip()
            if body:
                return body
        return None
