"""Wizard run-plan and screen preflight helpers."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.batch.manifest import find_screen_entry, load_batch_manifest
from figma_flutter_agent.batch.run import _figma_url_for_screen, _resolve_dump
from figma_flutter_agent.config import load_settings
from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
from figma_flutter_agent.dev.run import RunScreenPlan, detect_wired_screen_feature
from figma_flutter_agent.dev.wizard.asset_gap import resolve_screen_asset_icon_gap
from figma_flutter_agent.dev.wizard.models import ScreenPreflight


def build_run_plan(*, project_dir: Path, screen_name: str) -> RunScreenPlan:
    """Resolve manifest, config, dump, and Figma URL for ``screen_name``."""
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
        settings = load_settings(plan.config_path)
        expected_ids, covered_ids = resolve_screen_asset_icon_gap(
            dump_path=plan.dump_path,
            project_dir=plan.project_dir,
            file_key=plan.manifest.file_key,
            primary_node_id=plan.screen.node_id,
            assets=settings.agent.assets,
        )
        exportable_icons = len(expected_ids)
        local_icons = len(covered_ids)
        missing_asset_exports = len(expected_ids - covered_ids)

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


def missing_assets_hint(
    missing: int,
    *,
    prefer_live: bool = False,
    prefer_offline: bool = False,
    full_selected: bool = False,
) -> str:
    """Return a short hint for missing exported icons."""
    if prefer_offline:
        return f" ({missing} missing - offline run, no live asset sync)"
    if prefer_live:
        return f" ({missing} missing - will sync from Figma on run)"
    if full_selected:
        return f" ({missing} missing - set FIGMA_ACCESS_TOKEN to sync on run)"
    return f" ({missing} missing - live sync recommended)"


def format_screen_preflight(
    preflight: ScreenPreflight,
    *,
    prefer_live: bool = False,
    prefer_offline: bool = False,
    full_selected: bool = False,
) -> str:
    """Render a human-readable preflight summary."""
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
                missing_assets_hint(
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
