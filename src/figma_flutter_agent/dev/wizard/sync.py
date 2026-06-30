"""Sync-preview workflow helpers."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import Settings, load_settings
from figma_flutter_agent.dev.flutter_sdk import require_flutter_executable
from figma_flutter_agent.dev.run import RunScreenPlan, launch_flutter_app
from figma_flutter_agent.dev.wizard.models import ScreenPreflight
from figma_flutter_agent.dev.wizard.preflight import build_run_plan, collect_screen_preflight
from figma_flutter_agent.pipeline.result import PipelineResult
from figma_flutter_agent.pipeline.run import run_pipeline
from figma_flutter_agent.pipeline.warning_policy import (
    emit_user_warnings,
    is_actionable_user_warning,
)


def print_actionable_pipeline_warnings(warnings: list[str]) -> None:
    """Print asset and boundary warnings to the wizard console (always visible)."""
    from rich.console import Console

    console = Console()
    for message in warnings:
        if is_actionable_user_warning(message):
            console.print(f"[yellow]{message}[/yellow]")


async def generate_screen_for_preview(
    plan: RunScreenPlan,
    settings: Settings,
    *,
    live: bool,
    verbose: bool = False,
    force_llm_regen: bool = False,
    use_cached_ir: bool = False,
) -> PipelineResult:
    """Generate one screen using offline dump or live Figma sync."""
    result = await run_pipeline(
        settings,
        figma_url=plan.figma_url,
        project_dir=plan.project_dir,
        feature_name=plan.screen.feature,
        verbose=verbose,
        from_dump=None if live else plan.dump_path,
        from_ir=use_cached_ir,
        require_figma_token=live and not use_cached_ir,
        regenerate_templates=live,
        force_llm_regen=force_llm_regen,
        force_live_fetch=live,
    )
    emit_user_warnings(result.warnings, settings=settings)
    print_actionable_pipeline_warnings(result.warnings)
    logger.info(
        "Generated screen {} via {}",
        plan.screen.feature,
        "live Figma sync"
        if live
        else ("cached dump + screen IR" if use_cached_ir else "cached dump"),
    )
    return result


def resolve_live_sync(
    preflight: ScreenPreflight,
    *,
    has_figma_token: bool,
    prefer_live: bool | None,
) -> bool:
    """Decide whether sync-preview should fetch the frame from live Figma."""
    if prefer_live is True:
        return True
    if prefer_live is False:
        return False
    return preflight.needs_live_sync and has_figma_token


def finalize_sync_live_flag(
    preflight: ScreenPreflight,
    *,
    has_figma_token: bool,
    prefer_live: bool | None,
) -> bool:
    """Apply :func:`resolve_live_sync` plus the cached-dump safety guard."""
    live = resolve_live_sync(preflight, has_figma_token=has_figma_token, prefer_live=prefer_live)
    if preflight.dump_exists and prefer_live is not True:
        return False
    return live


async def sync_preview_workflow(
    *,
    project_dir: Path,
    screen_name: str,
    verbose: bool = False,
    prefer_live: bool | None = None,
    device_id: str | None = None,
    skip_launch: bool = False,
    settings: Settings | None = None,
    force_llm_regen: bool = False,
    use_cached_ir: bool = False,
) -> tuple[RunScreenPlan, bool | None, PipelineResult]:
    """Full sync-preview path: preflight -> generate -> optional ``flutter run``."""
    plan = build_run_plan(project_dir=project_dir, screen_name=screen_name)
    preflight = collect_screen_preflight(plan)

    resolved_settings = settings or load_settings(plan.config_path)
    has_token = bool(resolved_settings.figma_token().strip())
    if use_cached_ir:
        live = False
    else:
        live = finalize_sync_live_flag(
            preflight,
            has_figma_token=has_token,
            prefer_live=prefer_live,
        )

    if not preflight.dump_exists and not live:
        msg = (
            f"Dump missing for {screen_name}: {plan.dump_path.as_posix()}. "
            "Set FIGMA_ACCESS_TOKEN for live sync or run batch dump-file first."
        )
        raise FileNotFoundError(msg)
    if live and not has_token:
        msg = "FIGMA_ACCESS_TOKEN is required for live sync (missing icons or dump)."
        raise RuntimeError(msg)
    if preflight.missing_asset_exports and not live and not has_token:
        msg = (
            f"{preflight.missing_asset_exports} SVG icons missing for {screen_name}. "
            "Set FIGMA_ACCESS_TOKEN and choose live sync."
        )
        raise RuntimeError(msg)

    pipeline_result = await generate_screen_for_preview(
        plan,
        resolved_settings,
        live=live,
        verbose=verbose,
        force_llm_regen=force_llm_regen,
        use_cached_ir=use_cached_ir,
    )
    if skip_launch:
        return plan, None, pipeline_result
    launched = launch_flutter_app(
        plan.project_dir,
        device_id=device_id,
        flutter_sdk=resolved_settings.flutter_sdk or None,
        dump_path=plan.dump_path,
        settings=resolved_settings,
        feature_name=plan.screen.feature,
    )
    return plan, launched, pipeline_result


def run_flutter_analyze(
    project_dir: Path,
    *,
    flutter_sdk: str | Path | None = None,
    feature_name: str | None = None,
) -> None:
    """Run ``flutter analyze`` in the Flutter project."""
    from figma_flutter_agent.errors import FlutterProjectError
    from figma_flutter_agent.tools.process_run import (
        FLUTTER_ANALYZE_TIMEOUT_SEC,
        run_subprocess,
    )

    flutter = require_flutter_executable(sdk_root=flutter_sdk)
    result = run_subprocess(
        [flutter, "analyze"],
        cwd=project_dir,
        label="flutter analyze",
        timeout_sec=FLUTTER_ANALYZE_TIMEOUT_SEC,
        stream_output=True,
        project_dir=project_dir,
        feature_name=feature_name,
    )
    if result.returncode != 0:
        msg = f"flutter analyze failed (exit {result.returncode})"
        raise FlutterProjectError(msg)
