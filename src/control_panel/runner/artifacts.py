"""Zip debug artifacts and publish to the artifacts GitLab project."""

from __future__ import annotations

import json
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from control_panel.config.models import GitProvider
from control_panel.services.github import GitHubClient
from control_panel.services.gitlab import GitLabClient
from figma_flutter_agent.debug.paths import screen_root


def zip_screen_artifacts(
    *,
    project_dir: Path,
    feature_slug: str,
    job_id: str,
) -> Path:
    """Create a zip archive of one screen debug folder."""
    source = screen_root(project_dir, feature_slug)
    if not source.is_dir():
        msg = f"Debug artifacts missing: {source}"
        raise FileNotFoundError(msg)
    tmp_dir = Path(tempfile.mkdtemp(prefix="control-panel-artifacts-"))
    zip_path = tmp_dir / f"{job_id}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(source).as_posix())
    logger.info("Created artifact zip {} ({} bytes)", zip_path.as_posix(), zip_path.stat().st_size)
    return zip_path


async def publish_artifacts(
    *,
    gitlab: GitLabClient,
    artifacts_project_id: str,
    job_id: str,
    project_dir: Path,
    feature_slug: str,
    run_id: str,
    figma_url: str,
    discord_user_id: int,
    zip_path: Path,
    review_markdown: str,
) -> str:
    """Commit artifact zip and metadata to the artifacts repository."""
    now = datetime.now(UTC)
    prefix = f"runs/{now.year:04d}/{now.month:02d}/{now.day:02d}/{job_id}"
    metadata = {
        "jobId": job_id,
        "runId": run_id,
        "figmaUrl": figma_url,
        "discordUserId": str(discord_user_id),
        "projectDir": project_dir.as_posix(),
        "featureSlug": feature_slug,
        "createdAt": now.isoformat(),
    }
    meta_path = zip_path.parent / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    review_path = zip_path.parent / "review.md"
    review_path.write_text(review_markdown, encoding="utf-8")
    branch = "main"
    commit_url = await gitlab.commit_artifact_tree(
        project_id=artifacts_project_id,
        branch=branch,
        prefix=prefix,
        files={
            "artifacts.zip": zip_path,
            "metadata.json": meta_path,
            "review.md": review_path,
        },
        commit_message=f"artifacts: {job_id}",
    )
    return commit_url


async def publish_artifacts_remote(
    *,
    provider: GitProvider,
    remote: str,
    gitlab: GitLabClient | None,
    github: GitHubClient | None,
    job_id: str,
    project_dir: Path,
    feature_slug: str,
    run_id: str,
    figma_url: str,
    discord_user_id: int,
    zip_path: Path,
    review_markdown: str,
    branch: str = "main",
) -> str:
    """Commit artifact bundle to GitLab or GitHub artifacts repository."""
    now = datetime.now(UTC)
    prefix = f"runs/{now.year:04d}/{now.month:02d}/{now.day:02d}/{job_id}"
    metadata = {
        "jobId": job_id,
        "runId": run_id,
        "figmaUrl": figma_url,
        "discordUserId": str(discord_user_id),
        "projectDir": project_dir.as_posix(),
        "featureSlug": feature_slug,
        "createdAt": now.isoformat(),
    }
    meta_path = zip_path.parent / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    review_path = zip_path.parent / "review.md"
    review_path.write_text(review_markdown, encoding="utf-8")
    files = {
        f"{prefix}/artifacts.zip": zip_path,
        f"{prefix}/metadata.json": meta_path,
        f"{prefix}/review.md": review_path,
    }
    if provider == GitProvider.GITHUB:
        if github is None:
            return ""
        commit = await github.commit_files(
            branch=branch,
            commit_message=f"artifacts: {job_id}",
            files=files,
            start_branch=branch,
        )
        return str(commit.get("web_url") or "")
    if gitlab is None:
        return ""
    return await gitlab.commit_artifact_tree(
        project_id=remote,
        branch=branch,
        prefix=prefix,
        files={
            "artifacts.zip": zip_path,
            "metadata.json": meta_path,
            "review.md": review_path,
        },
        commit_message=f"artifacts: {job_id}",
    )
