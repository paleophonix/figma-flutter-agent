"""Persist AI UX and animation reports for optional spec §21 / §22 features."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.parser.accessibility import collect_accessibility_warnings
from figma_flutter_agent.parser.animations import (
    build_animation_manifest,
    collect_animation_suggestions,
)
from figma_flutter_agent.parser.prototype import PrototypeLink
from figma_flutter_agent.parser.transitions import PrototypeTransition
from figma_flutter_agent.parser.ux import collect_ux_suggestions
from figma_flutter_agent.schemas import CleanDesignTreeNode


def build_ai_ux_report(
    root: CleanDesignTreeNode,
    *,
    prototype_links: list[PrototypeLink] | None = None,
    route_transitions: dict[str, PrototypeTransition] | None = None,
    routing_type: str = "none",
    dark_mode_enabled: bool = False,
) -> dict[str, Any]:
    """Aggregate heuristic UX, accessibility, and animation suggestions."""
    ux = collect_ux_suggestions(root)
    accessibility = collect_accessibility_warnings(root)
    animation = collect_animation_suggestions(
        prototype_links or [],
        route_transitions=route_transitions,
    )
    if not dark_mode_enabled:
        animation.append(
            "Dark mode is disabled; enable dark_mode.enabled in .ai-figma-flutter.yml "
            "enable dark_mode.enabled in .ai-figma-flutter.yml to generate light/dark AppTheme variants."
        )
    return {
        "aiUxSuggestions": ux,
        "accessibilityWarnings": accessibility,
        "animationSuggestions": animation,
        "animationManifest": build_animation_manifest(
            prototype_links or [],
            route_transitions=route_transitions,
            routing_type=routing_type,
        ),
    }


def write_analysis_reports(
    project_dir: Path,
    *,
    feature_slug: str,
    root: CleanDesignTreeNode,
    prototype_links: list[PrototypeLink] | None = None,
    route_transitions: dict[str, PrototypeTransition] | None = None,
    routing_type: str = "none",
    dark_mode_enabled: bool = False,
    write_ux_report: bool = True,
    write_animation_manifest: bool = True,
) -> list[Path]:
    """Write optional JSON reports under ``.figma_debug/reports``."""
    if not write_ux_report and not write_animation_manifest:
        return []

    report_dir = project_dir / ".figma_debug" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if write_ux_report:
        payload = build_ai_ux_report(
            root,
            prototype_links=prototype_links,
            route_transitions=route_transitions,
            routing_type=routing_type,
            dark_mode_enabled=dark_mode_enabled,
        )
        ux_path = report_dir / f"{feature_slug}_ai_ux.json"
        ux_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(ux_path)
        logger.info("Wrote AI UX report to {}", ux_path.as_posix())
        from figma_flutter_agent.debug.mirror import mirror_figma_debug_artifact

        mirror_figma_debug_artifact(project_dir, ux_path)

    if write_animation_manifest:
        manifest = build_animation_manifest(
            prototype_links or [],
            route_transitions=route_transitions,
            routing_type=routing_type,
        )
        anim_path = report_dir / f"{feature_slug}_animations.json"
        anim_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(anim_path)
        logger.info("Wrote animation manifest to {}", anim_path.as_posix())
        from figma_flutter_agent.debug.mirror import mirror_figma_debug_artifact

        mirror_figma_debug_artifact(project_dir, anim_path)

    return written
