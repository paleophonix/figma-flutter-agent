"""Interactive wizard workflows: preflight, doctor, sync-preview, Flutter helpers."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.assets.exporter import collect_exportable_nodes
from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids
from figma_flutter_agent.batch.manifest import find_screen_entry, load_batch_manifest
from figma_flutter_agent.batch.run import _figma_url_for_screen, _resolve_dump
from figma_flutter_agent.config import Settings, load_settings
from figma_flutter_agent.dev.flutter_sdk import (
    require_flutter_executable,
    resolve_dart_executable,
    resolve_flutter_executable,
)
from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
from figma_flutter_agent.dev.run import (
    RunScreenPlan,
    detect_wired_screen_feature,
    launch_flutter_app,
)
from figma_flutter_agent.fonts.diagnostics import collect_font_audit_rows
from figma_flutter_agent.pipeline import PipelineResult, run_pipeline
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.pipeline.warning_policy import emit_user_warnings

_AGENT_REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class DoctorCheck:
    """One environment readiness check."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    """Aggregated wizard environment report."""

    checks: tuple[DoctorCheck, ...]

    @property
    def passed(self) -> bool:
        """Return True when every check succeeded."""
        return all(item.ok for item in self.checks)


@dataclass(frozen=True)
class ScreenPreflight:
    """Readiness summary for one manifest screen."""

    feature: str
    dump_exists: bool
    dump_path: Path | None
    wired_feature: str | None
    wired_matches: bool
    exportable_icons: int
    local_icons: int
    missing_asset_exports: int

    @property
    def needs_live_sync(self) -> bool:
        """Return True when a live Figma frame fetch is required (no cached dump)."""
        return not self.dump_exists

    @property
    def needs_live_asset_sync(self) -> bool:
        """Return True when SVG/raster assets are missing on disk but a dump exists."""
        return self.dump_exists and self.missing_asset_exports > 0


def agent_repo_root() -> Path:
    """Return the figma-flutter-agent repository root."""
    return _AGENT_REPO_ROOT


def build_run_plan(*, project_dir: Path, screen_name: str) -> RunScreenPlan:
    """Resolve manifest, config, dump, and Figma URL for ``screen_name``.

    Unlike ``plan_run_screen``, this does not require a cached dump file.
    """
    config_path = ensure_project_config(project_dir)
    manifest = load_batch_manifest(resolve_manifest_path(project_dir))
    screen = find_screen_entry(manifest, screen_name)
    dump_path = _resolve_dump(screen, manifest.project_dir)
    return RunScreenPlan(
        project_dir=manifest.project_dir,
        config_path=config_path,
        manifest=manifest,
        screen=screen,
        dump_path=dump_path,
        figma_url=_figma_url_for_screen(manifest, screen),
    )


def collect_screen_preflight(plan: RunScreenPlan) -> ScreenPreflight:
    """Inspect dump, wiring, and exported SVG coverage for a screen."""
    wired = detect_wired_screen_feature(plan.project_dir)
    dump_exists = plan.dump_path.is_file()
    exportable_icons = 0
    missing_asset_exports = 0
    local_icons = 0

    if dump_exists:
        root = json.loads(plan.dump_path.read_text(encoding="utf-8"))
        exclude_ids = build_screen_frame_exclude_ids(plan.screen.node_id)
        icon_ids = {
            node_id
            for node_id, _, kind in collect_exportable_nodes(
                root,
                exclude_node_ids=set(exclude_ids),
            )
            if kind == "icon"
        }
        exportable_icons = len(icon_ids)
        local_ids = {
            entry.node_id
            for entry in local_asset_manifest_from_project(
                plan.project_dir,
                exclude_node_ids=exclude_ids,
            ).entries
        }
        local_icons = len(local_ids)
        missing_asset_exports = len(icon_ids - local_ids)

    return ScreenPreflight(
        feature=plan.screen.feature,
        dump_exists=dump_exists,
        dump_path=plan.dump_path if dump_exists else None,
        wired_feature=wired,
        wired_matches=wired == plan.screen.feature,
        exportable_icons=exportable_icons,
        local_icons=local_icons,
        missing_asset_exports=missing_asset_exports,
    )


def _missing_assets_hint(
    missing: int,
    *,
    prefer_live: bool = False,
    prefer_offline: bool = False,
    full_selected: bool = False,
) -> str:
    """Return a short hint for missing exported icons."""
    if prefer_offline:
        return f" ({missing} missing — offline run, no live asset sync)"
    if prefer_live:
        return f" ({missing} missing — will sync from Figma on run)"
    if full_selected:
        return f" ({missing} missing — set FIGMA_ACCESS_TOKEN to sync on run)"
    return f" ({missing} missing — live sync recommended)"


def format_screen_preflight(
    preflight: ScreenPreflight,
    *,
    prefer_live: bool = False,
    prefer_offline: bool = False,
    full_selected: bool = False,
) -> str:
    """Render a human-readable preflight summary.

    Args:
        preflight: Collected dump/wiring/asset coverage for the screen.
        prefer_live: True when the run pipeline will sync from live Figma.
        prefer_offline: True when the user chose offline run (cached dump only).
        full_selected: True when the user chose full run but live sync is unavailable.
    """
    lines = [
        f"Screen: {preflight.feature}",
        f"Dump: {'OK' if preflight.dump_exists else 'missing'}"
        + (f" ({preflight.dump_path.as_posix()})" if preflight.dump_path else ""),
        f"main.dart wired: {preflight.wired_feature or 'unknown'}"
        + (" (match)" if preflight.wired_matches else " (mismatch)"),
    ]
    if preflight.dump_exists:
        lines.append(
            f"Icons: {preflight.local_icons} on disk / {preflight.exportable_icons} in dump"
            + (
                _missing_assets_hint(
                    preflight.missing_asset_exports,
                    prefer_live=prefer_live,
                    prefer_offline=prefer_offline,
                    full_selected=full_selected,
                )
                if preflight.missing_asset_exports
                else " (complete)"
            )
        )
    elif preflight.needs_live_sync:
        lines.append("Live Figma sync required (no cached dump).")
    return "\n".join(lines)


def collect_doctor_report(*, project_dir: Path, settings: Settings) -> DoctorReport:
    """Run environment checks for the interactive wizard."""
    checks: list[DoctorCheck] = []

    token = settings.figma_token().strip()
    checks.append(
        DoctorCheck(
            name="FIGMA_ACCESS_TOKEN",
            ok=bool(token),
            detail="present" if token else "missing — live sync and batch dump need a token",
        )
    )

    flutter = resolve_flutter_executable(sdk_root=settings.flutter_sdk or None)
    checks.append(
        DoctorCheck(
            name="Flutter SDK",
            ok=flutter is not None,
            detail=flutter or "not on PATH — set FIGMA_FLUTTER_SDK in .env",
        )
    )

    dart = resolve_dart_executable(sdk_root=settings.flutter_sdk or None)
    checks.append(
        DoctorCheck(
            name="Dart SDK",
            ok=dart is not None,
            detail=dart or "not on PATH (optional for analyze gates)",
        )
    )

    pubspec = project_dir / "pubspec.yaml"
    checks.append(
        DoctorCheck(
            name="Flutter project",
            ok=pubspec.is_file(),
            detail=project_dir.as_posix() if pubspec.is_file() else "pubspec.yaml not found",
        )
    )

    manifest_path = resolve_manifest_path(project_dir)
    checks.append(
        DoctorCheck(
            name="screens.yaml",
            ok=manifest_path.is_file(),
            detail=manifest_path.as_posix()
            if manifest_path.is_file()
            else "batch manifest missing",
        )
    )

    from figma_flutter_agent.config import resolve_agent_config_path

    config_path = resolve_agent_config_path()
    checks.append(
        DoctorCheck(
            name="agent config (.ai-figma-flutter.yml)",
            ok=config_path.is_file(),
            detail=config_path.as_posix(),
        )
    )

    env_project = settings.default_project_dir
    if env_project:
        checks.append(
            DoctorCheck(
                name="FIGMA_FLUTTER_PROJECT_DIR",
                ok=Path(env_project).expanduser().is_dir(),
                detail=str(env_project),
            )
        )

    for row in collect_font_audit_rows(project_dir):
        checks.append(DoctorCheck(name=row.name, ok=row.ok, detail=row.detail))

    return DoctorReport(checks=tuple(checks))


def format_doctor_report(report: DoctorReport) -> str:
    """Render doctor checks for the wizard."""
    lines: list[str] = []
    for item in report.checks:
        status = "OK" if item.ok else "FAIL"
        lines.append(f"  [{status}] {item.name}: {item.detail}")
    summary = "All checks passed." if report.passed else "Some checks failed."
    return summary + "\n" + "\n".join(lines)


def list_flutter_devices(*, flutter_sdk: str | Path | None = None) -> list[tuple[str, str]]:
    """Return Flutter device ids and labels from ``flutter devices --machine``."""
    flutter = resolve_flutter_executable(sdk_root=flutter_sdk)
    if flutter is None:
        return []

    result = subprocess.run(
        [flutter, "devices", "--machine"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            payload = json.loads(result.stdout)
            devices: list[tuple[str, str]] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                device_id = item.get("id")
                if not device_id:
                    continue
                name = str(item.get("name") or device_id)
                platform = str(item.get("targetPlatform") or item.get("platform") or "unknown")
                devices.append((str(device_id), f"{name} ({platform})"))
            if devices:
                return devices
        except json.JSONDecodeError:
            logger.debug("Could not parse flutter devices --machine output")

    fallback = subprocess.run(
        [flutter, "devices"],
        capture_output=True,
        text=True,
        check=False,
    )
    if fallback.returncode != 0:
        return []

    devices = []
    for line in fallback.stdout.splitlines():
        match = re.match(r"^\s*(.+?) \(mobile|desktop|web\)\s•\s(.+?) •", line)
        if match:
            devices.append((match.group(2).strip(), match.group(1).strip()))
    return devices


def device_id_from_choice(label: str) -> str | None:
    """Extract a Flutter device id from a wizard choice label."""
    match = re.search(r"\[(.+?)\]\s*$", label)
    if match:
        return match.group(1)
    return None


def default_flutter_device_option(devices: list[tuple[str, str]]) -> str | None:
    """Return the wizard menu label for the preferred default ``flutter run`` target.

    Prefers Chrome on ``web-javascript`` when present, otherwise the first device.

    Args:
        devices: ``(device_id, label)`` pairs from :func:`list_flutter_devices`.

    Returns:
        A choice string like ``Chrome (web-javascript) [chrome]``, or ``None`` when
        ``devices`` is empty.
    """
    if not devices:
        return None

    def _option(device_id: str, label: str) -> str:
        return f"{label} [{device_id}]"

    for device_id, label in devices:
        lowered_id = device_id.lower()
        lowered_label = label.lower()
        if lowered_id == "chrome" or (
            "chrome" in lowered_label and "web-javascript" in lowered_label
        ):
            return _option(device_id, label)

    for device_id, label in devices:
        if "web-javascript" in label.lower():
            return _option(device_id, label)

    device_id, label = devices[0]
    return _option(device_id, label)


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
    """Decide whether sync-preview should fetch the frame from live Figma.

    Missing on-disk icons alone do not force a live frame fetch when a cached dump
    exists; use ``batch dump-file`` media mode or explicit full run for asset backfill.
    """
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
    """Apply :func:`resolve_live_sync` plus the cached-dump safety guard.

    When a dump file exists, live frame fetch runs only for explicit full sync
    (``prefer_live is True``).
    """
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
    """Full sync-preview path: preflight → generate → optional ``flutter run``."""
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
    )
    return plan, launched, pipeline_result


def run_flutter_analyze(project_dir: Path, *, flutter_sdk: str | Path | None = None) -> None:
    """Run ``flutter analyze`` in the Flutter project."""
    flutter = require_flutter_executable(sdk_root=flutter_sdk)
    subprocess.run([flutter, "analyze"], cwd=project_dir, check=True)


def run_agent_signoff(*, agent_root: Path | None = None) -> None:
    """Run offline agent release checks (demo-signoff + pytest)."""
    root = agent_root or agent_repo_root()
    subprocess.run(
        [
            "poetry",
            "run",
            "figma-flutter",
            "demo-signoff",
            "--strict",
            "--signoff-gates",
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["poetry", "run", "pytest", "-q", "-m", "not live_figma"],
        cwd=root,
        check=True,
    )
