"""In-process publish entrypoints for CLI and wizard."""

from __future__ import annotations

from pathlib import Path

from control_panel.config import load_discord_bot_settings
from control_panel.db.engine import create_engine, create_session_factory
from control_panel.db.models import Base
from control_panel.db.store import JobStore
from control_panel.publish.orchestrate import run_publish_for_job
from figma_flutter_agent.errors import FigmaFlutterError


async def publish_project_dir(
    *,
    project_dir: Path,
    repo_key: str,
    mode: str,
    target_file: str | None,
    feature_slug: str | None = None,
    figma_url: str = "",
) -> str:
    """Publish a generated project directory in-process (CLI/wizard)."""
    try:
        settings = load_discord_bot_settings(require_discord_token=False)
    except FigmaFlutterError as exc:
        raise FigmaFlutterError(
            "Control panel is not configured. Install the control_panel extra and copy .control-panel.yml."
        ) from exc
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    store = JobStore(create_session_factory(engine))
    job = await store.create_job(
        job_id=f"cli-{project_dir.name}",
        figma_url=figma_url or "cli://local",
        discord_user_id=0,
        discord_channel_id=0,
        project_dir=project_dir.resolve(),
        repo_key=repo_key,
        target_mode=mode,
        target_file_path=target_file,
    )
    if feature_slug:
        await store.update_job(job.id, feature_slug=feature_slug)
    refreshed = await store.get_job(job.id)
    if refreshed is None:
        raise FigmaFlutterError("Publish job was not created.")
    result = await run_publish_for_job(settings=settings, store=store, job=refreshed)
    await engine.dispose()
    return result.pr_url
