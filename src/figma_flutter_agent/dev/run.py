"""Generate one screen and launch the Flutter app."""

from __future__ import annotations

import asyncio
import re
import subprocess
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
from figma_flutter_agent.dev.flutter_sdk import require_flutter_executable
from figma_flutter_agent.dev.preview_size import (
    chrome_preview_launch_flags,
    is_chrome_device,
    prepare_artboard_chrome_launch,
)
from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.pipeline import run_pipeline


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
        require_figma_token=False,
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


def _flutter_run_stopped(returncode: int | None) -> bool:
    """Return True when ``flutter run`` was stopped interactively."""
    if returncode in {0, None}:
        return False
    if returncode in {130, 255, 3221225786, -1073741510}:
        return True
    return returncode < 0


def _run_flutter_command(
    cmd: list[str],
    *,
    project_dir: Path,
    action: str,
) -> None:
    """Run a Flutter CLI command and map failures to ``FlutterProjectError``."""
    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
    except subprocess.CalledProcessError as exc:
        logger.error("{} failed (exit {})", action, exc.returncode)
        msg = f"{action} failed (exit {exc.returncode})"
        raise FlutterProjectError(msg) from exc


def launch_flutter_app(
    project_dir: Path,
    *,
    device_id: str | None = None,
    flutter_sdk: str | Path | None = None,
    preview_size: tuple[int, int] | None = None,
    dump_path: Path | None = None,
) -> bool:
    """Run ``flutter pub get`` and ``flutter run`` in ``project_dir``.

    Args:
        project_dir: Flutter project root.
        device_id: Optional ``flutter run -d`` target id.
        flutter_sdk: Optional Flutter SDK root when not on PATH.
        preview_size: Optional ``(width, height)`` artboard size for Chrome window
            flags so the debug browser matches the rendered Figma frame.
        dump_path: Optional cached layout dump; when set, infers artboard size and
            defaults the launch target to Chrome for wizard-style preview.

    Returns:
        True when ``flutter run`` exits cleanly; False when the user stops it.

    Raises:
        FlutterProjectError: When ``pub get`` or ``flutter run`` fails.
    """
    device_id, preview_size = prepare_artboard_chrome_launch(
        device_id=device_id,
        flutter_sdk=flutter_sdk,
        preview_size=preview_size,
        dump_path=dump_path,
    )
    flutter = require_flutter_executable(sdk_root=flutter_sdk)
    logger.info("Running flutter pub get in {}", project_dir.as_posix())
    _run_flutter_command(
        [flutter, "pub", "get"],
        project_dir=project_dir,
        action="flutter pub get",
    )
    run_cmd = [flutter, "run", "--no-pub"]
    if device_id:
        run_cmd.extend(["-d", device_id])
    if preview_size is not None and is_chrome_device(device_id):
        width, height = preview_size
        run_cmd.extend(chrome_preview_launch_flags(width, height))
        logger.info("Chrome artboard preview {}x{} (1:1, no shell margins)", width, height)
    device_label = device_id or "default device"
    logger.info("Launching flutter run on {} in {}", device_label, project_dir.as_posix())
    try:
        subprocess.run(run_cmd, cwd=project_dir, check=True)
    except subprocess.CalledProcessError as exc:
        if _flutter_run_stopped(exc.returncode):
            logger.info("Flutter run stopped (exit {})", exc.returncode)
            return False
        msg = f"flutter run failed (exit {exc.returncode})"
        raise FlutterProjectError(msg) from exc
    return True


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
