"""Thin wrapper: shared repair pipeline for control plane (M6)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.dev.opencode import OpenCodeClient
from figma_flutter_agent.dev.opencode.opencode_policy import (
    build_opencode_overlay,
    prompt_options_for_write_step,
)
from figma_flutter_agent.dev.opencode.pipeline import PipelineOutcome, run_repair_pipeline
from figma_flutter_agent.dev.opencode.provider_preflight import (
    verify_opencode_openrouter_connectivity,
)
from figma_flutter_agent.dev.opencode.runtime import ensure_opencode_serve
from figma_flutter_agent.errors import LlmError


async def run_headless_repair_case(
    *,
    settings: Settings,
    project_dir: Path,
    feature: str,
    skip_opencode_repair: bool = False,
) -> PipelineOutcome:
    """Run the wizard repair pipeline from control plane workers."""
    pipeline = settings.agent.debug_pipeline
    api_key = settings.openrouter_api_key.get_secret_value().strip()
    if not skip_opencode_repair and not api_key:
        raise LlmError(
            "OPENROUTER_API_KEY is required for headless repair "
            "(OpenCode serve calls OpenRouter for repair/fix write steps)."
        )

    await ensure_opencode_serve(
        base_url=settings.opencode_base_url,
        password=settings.opencode_server_password.get_secret_value(),
        config_overlay=build_opencode_overlay(
            pipeline,
            openrouter_api_key=api_key or None,
        ),
        openrouter_api_key=api_key or None,
        restart_with_overlay=pipeline.loops.restart_opencode_serve_with_overlay,
    )

    opencode_client: OpenCodeClient | None = None
    if not skip_opencode_repair:
        repair_prompt = prompt_options_for_write_step(pipeline, step="repair")
        await verify_opencode_openrouter_connectivity(
            base_url=settings.opencode_base_url,
            password=settings.opencode_server_password.get_secret_value(),
            model=str(repair_prompt["model"]),
            reasoning_effort=repair_prompt["reasoning_effort"],
        )
        opencode_client = OpenCodeClient(
            base_url=settings.opencode_base_url,
            password=settings.opencode_server_password.get_secret_value(),
            timeout_sec=(
                float(pipeline.loops.opencode_prompt_timeout_sec)
                if pipeline.loops.opencode_prompt_timeout_sec is not None
                else None
            ),
        )

    return await run_repair_pipeline(
        settings=settings,
        project_dir=project_dir,
        feature=feature,
        opencode_client=opencode_client,
        skip_opencode_repair=skip_opencode_repair,
        command="control_plane_repair",
    )
