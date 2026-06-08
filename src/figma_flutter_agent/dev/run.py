"""Generate one screen and launch the Flutter app."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.batch.manifest import (
    BatchManifest,
    ScreenEntry,
    find_screen_entry,
    load_batch_manifest,
)
from figma_flutter_agent.batch.run import _figma_url_for_screen, _resolve_dump
from figma_flutter_agent.config import Settings, apply_production_profile, load_settings
from figma_flutter_agent.dev.flutter_launch import (
    launch_flutter_app,
    reap_stale_flutter_web_processes,
)
from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
from figma_flutter_agent.pipeline.run import run_pipeline


@dataclass(frozen=True)
class RunScreenPlan:
    """Resolved inputs for a one-command dev run."""

    project_dir: Path
    config_path: Path
    manifest: BatchManifest
    screen: ScreenEntry
    dump_path: Path
    figma_url: str


def plan_run_screen(
    *,
    project_dir: Path,
    screen_name: str,
) -> RunScreenPlan:
    """Resolve manifest, config, and dump paths for ``screen_name``."""
    config_path = ensure_project_config(project_dir)
    manifest_path = resolve_manifest_path(project_dir)
    manifest = load_batch_manifest(manifest_path)
    screen = find_screen_entry(manifest, screen_name)
    dump_path = _resolve_dump(screen, manifest.project_dir)
    if not dump_path.is_file():
        msg = (
            f"Dump missing for {screen.feature}: {dump_path.as_posix()}. "
            "Run `figma-flutter batch dump-file --project-dir ...` first."
        )
        raise FileNotFoundError(msg)
    return RunScreenPlan(
        project_dir=manifest.project_dir,
        config_path=config_path,
        manifest=manifest,
        screen=screen,
        dump_path=dump_path,
        figma_url=_figma_url_for_screen(manifest, screen),
    )


def detect_wired_screen_feature(project_dir: Path) -> str | None:
    """Return the feature slug wired in ``lib/main.dart``, if detectable."""
    main_dart = project_dir / "lib" / "main.dart"
    if not main_dart.is_file():
        return None
    text = main_dart.read_text(encoding="utf-8")
    for pattern in (
        r"features/(?P<feature>[a-z0-9_]+)/(?P=feature)_screen\.dart",
        r"presentation/screens/(?P<feature>[a-z0-9_]+)_screen\.dart",
    ):
        match = re.search(pattern, text)
        if match is not None:
            return match.group("feature")
    return None


async def generate_run_screen(
    plan: RunScreenPlan,
    settings: Settings,
    *,
    verbose: bool = False,
) -> None:
    """Generate Flutter code for the selected screen and wire ``main.dart``."""
    await run_pipeline(
        settings,
        figma_url=plan.figma_url,
        project_dir=plan.project_dir,
        feature_name=plan.screen.feature,
        verbose=verbose,
        from_dump=plan.dump_path,
        from_ir=True,
        require_figma_token=False,
        force_llm_regen=False,
    )
    logger.info("Generated screen {} for dev run", plan.screen.feature)


def wire_active_screen_blocking(
    *,
    project_dir: Path,
    screen_name: str,
    allow_dev_profile: bool = True,
    verbose: bool = False,
) -> RunScreenPlan:
    """Generate one screen and wire ``main.dart`` without launching Flutter."""
    plan = plan_run_screen(project_dir=project_dir, screen_name=screen_name)
    settings = load_settings(plan.config_path)
    if not allow_dev_profile:
        settings = apply_production_profile(settings)

    async def _run() -> None:
        await generate_run_screen(plan, settings, verbose=verbose)

    asyncio.run(_run())
    return plan


async def run_screen_workflow(
    *,
    project_dir: Path,
    screen_name: str,
    skip_generate: bool = False,
    allow_dev_profile: bool = True,
    verbose: bool = False,
    device_id: str | None = None,
    flutter_sdk: str | Path | None = None,
) -> tuple[RunScreenPlan, bool]:
    """Generate (optional) and launch one manifest screen."""
    plan = plan_run_screen(project_dir=project_dir, screen_name=screen_name)
    if not skip_generate:
        settings = load_settings(plan.config_path)
        if not allow_dev_profile:
            settings = apply_production_profile(settings)
        await generate_run_screen(plan, settings, verbose=verbose)
    launched = launch_flutter_app(
        plan.project_dir,
        device_id=device_id,
        flutter_sdk=flutter_sdk,
        dump_path=plan.dump_path,
    )
    return plan, launched


def run_screen_blocking(
    *,
    project_dir: Path,
    screen_name: str,
    skip_generate: bool = False,
    allow_dev_profile: bool = True,
    verbose: bool = False,
    device_id: str | None = None,
    flutter_sdk: str | Path | None = None,
) -> tuple[RunScreenPlan, bool]:
    """Sync wrapper around ``run_screen_workflow``."""
    return asyncio.run(
        run_screen_workflow(
            project_dir=project_dir,
            screen_name=screen_name,
            skip_generate=skip_generate,
            allow_dev_profile=allow_dev_profile,
            verbose=verbose,
            device_id=device_id,
            flutter_sdk=flutter_sdk,
        )
    )
