"""Persist AI UX and animation reports for optional spec §21 / §22 features."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.debug.paths import (
    ai_ux_report_path,
    animations_report_path,
)
from figma_flutter_agent.generator.checks.layout import layout_tier_warning_message
from figma_flutter_agent.parser.accessibility import collect_accessibility_warnings
from figma_flutter_agent.parser.animations import (
    build_animation_manifest,
    collect_animation_suggestions,
)
from figma_flutter_agent.parser.prototype import PrototypeLink
from figma_flutter_agent.parser.transitions import PrototypeTransition
from figma_flutter_agent.parser.ux import (
    collect_ux_suggestions,
    resolve_layout_tier_from_source,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode


def build_ai_ux_report(
    root: CleanDesignTreeNode,
    *,
    prototype_links: list[PrototypeLink] | None = None,
    route_transitions: dict[str, PrototypeTransition] | None = None,
    routing_type: str = "none",
    dark_mode_enabled: bool = False,
    layout_source: str | None = None,
    responsive_enabled: bool = False,
) -> dict[str, Any]:
    """Aggregate heuristic UX, accessibility, and animation suggestions."""
    ux = collect_ux_suggestions(
        root,
        layout_source=layout_source,
        responsive_enabled=responsive_enabled,
    )
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
        "layoutTier": resolve_layout_tier_from_source(layout_source, root_type=root.type),
        "aiUxSuggestions": ux,
        "accessibilityWarnings": accessibility,
        "animationSuggestions": animation,
        "animationManifest": build_animation_manifest(
            prototype_links or [],
            route_transitions=route_transitions,
            routing_type=routing_type,
        ),
    }


def augment_ai_ux_report_layout_tier(
    project_dir: Path,
    feature_slug: str,
    *,
    layout_source: str,
    root: CleanDesignTreeNode,
    responsive_enabled: bool,
) -> Path | None:
    """Merge ``layoutTier`` into an existing AI UX report after layout emit."""
    ux_path = ai_ux_report_path(project_dir, feature_slug)
    if ux_path.is_file():
        payload = json.loads(ux_path.read_text(encoding="utf-8"))
    else:
        payload = build_ai_ux_report(
            root,
            responsive_enabled=responsive_enabled,
        )
    tier = resolve_layout_tier_from_source(layout_source, root_type=root.type)
    payload["layoutTier"] = tier
    suggestions = list(payload.get("aiUxSuggestions") or [])
    if responsive_enabled and tier:
        tier_message = layout_tier_warning_message(tier)
        if tier_message and tier_message not in suggestions:
            suggestions.append(tier_message)
    payload["aiUxSuggestions"] = suggestions
    ux_path.parent.mkdir(parents=True, exist_ok=True)
    ux_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return ux_path


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
    """Write optional JSON reports under ``.debug/<feature>/secondary/``."""
    if not write_ux_report and not write_animation_manifest:
        return []

    written: list[Path] = []

    if write_ux_report:
        payload = build_ai_ux_report(
            root,
            prototype_links=prototype_links,
            route_transitions=route_transitions,
            routing_type=routing_type,
            dark_mode_enabled=dark_mode_enabled,
        )
        ux_path = ai_ux_report_path(project_dir, feature_slug)
        ux_path.parent.mkdir(parents=True, exist_ok=True)
        ux_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(ux_path)
        logger.info("Wrote AI UX report to {}", ux_path.as_posix())

    if write_animation_manifest:
        manifest = build_animation_manifest(
            prototype_links or [],
            route_transitions=route_transitions,
            routing_type=routing_type,
        )
        anim_path = animations_report_path(project_dir, feature_slug)
        anim_path.parent.mkdir(parents=True, exist_ok=True)
        anim_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(anim_path)
        logger.info("Wrote animation manifest to {}", anim_path.as_posix())

    return written
