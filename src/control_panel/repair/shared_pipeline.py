"""Thin wrapper: shared repair pipeline for control plane (M6)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.dev.opencode.opencode_policy import build_opencode_overlay
from figma_flutter_agent.dev.opencode.pipeline import PipelineOutcome, run_repair_pipeline
from figma_flutter_agent.dev.opencode.runtime import ensure_opencode_serve


async def run_headless_repair_case(
    *,
    settings: Settings,
    project_dir: Path,
    feature: str,
    skip_opencode_repair: bool = False,
) -> PipelineOutcome:
    """Run the wizard repair pipeline from control plane workers."""
    pipeline = settings.agent.debug_pipeline
    await ensure_opencode_serve(
        base_url=settings.opencode_base_url,
        password=settings.opencode_server_password.get_secret_value(),
        config_overlay=build_opencode_overlay(pipeline),
    )
    return await run_repair_pipeline(
        settings=settings,
        project_dir=project_dir,
        feature=feature,
        skip_opencode_repair=skip_opencode_repair,
    )
