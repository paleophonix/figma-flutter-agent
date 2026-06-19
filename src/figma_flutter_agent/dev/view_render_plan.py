"""Planned-file preparation for wizard render previews."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.dart_bundle_parse import (
    detect_screen_class_from_planned_files,
    planned_files_from_dart_bundle,
)
from figma_flutter_agent.debug.paths import resolve_processed_dump_path
from figma_flutter_agent.generator.pubspec import read_pubspec_name
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.schemas import CleanDesignTreeNode

CaptureSourceMode = Literal["exact_bundle", "refreshed_clean_tree"]
CaptureTargetSource = Literal["debug_bundle", "pipeline_planned"]

EXACT_BUNDLE_SOURCE_MODE: CaptureSourceMode = "exact_bundle"
REFRESHED_CLEAN_TREE_SOURCE_MODE: CaptureSourceMode = "refreshed_clean_tree"

MIXED_SOURCE_ORACLE_WARNING = (
    "Mixed-source oracle: capture layout was re-emitted from cleanTree without screen IR; "
    "pixel diff vs Chrome/debug bundle is not trustworthy for visual repair."
)


@dataclass(frozen=True)
class CapturePlanResult:
    """Planned capture workspace files plus source identity for oracle manifests."""

    planned: dict[str, str]
    source_mode: CaptureSourceMode
    target_source: CaptureTargetSource
    bundle_path: str | None = None
    bundle_hash: str | None = None
    layout_hash: str | None = None
    screen_hash: str | None = None


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest of UTF-8 text."""
    return hashlib.sha256(text.encode()).hexdigest()


def planned_file_hashes(
    planned: dict[str, str],
    feature_name: str,
) -> tuple[str | None, str | None]:
    """Hash layout and screen entries from a planned map."""
    layout_key = f"lib/generated/{feature_name}_layout.dart"
    screen_key = f"lib/features/{feature_name}/{feature_name}_screen.dart"
    layout_hash = sha256_text(planned[layout_key]) if layout_key in planned else None
    screen_hash = sha256_text(planned[screen_key]) if screen_key in planned else None
    return layout_hash, screen_hash


def oracle_visual_repair_eligible(source_mode: str | None) -> bool:
    """Return whether capture-vs-Chrome diff may feed visual repair loops."""
    if source_mode is None:
        return True
    return source_mode == EXACT_BUNDLE_SOURCE_MODE


def load_clean_tree_from_debug(
    project_dir: Path,
    feature_name: str,
) -> CleanDesignTreeNode | None:
    """Load ``cleanTree`` from ``.debug/<feature>/primary/processed.json``."""
    processed = resolve_processed_dump_path(project_dir, feature_name)
    if processed is None:
        return None
    payload = json.loads(processed.read_text(encoding="utf-8"))
    tree_payload = payload.get("cleanTree")
    if tree_payload is None:
        return None
    return CleanDesignTreeNode.model_validate(tree_payload)


def artboard_size(clean_tree: CleanDesignTreeNode | None) -> tuple[int, int]:
    """Return the render surface size for a clean tree."""
    if clean_tree is None:
        return 390, 844
    width = clean_tree.sizing.width
    height = clean_tree.sizing.height
    surface_width = max(int(width), 1) if isinstance(width, (int, float)) and width > 0 else 390
    surface_height = max(int(height), 1) if isinstance(height, (int, float)) and height > 0 else 844
    return surface_width, surface_height


def refresh_planned_layout_from_clean_tree(
    planned: dict[str, str],
    *,
    feature_name: str,
    clean_tree: CleanDesignTreeNode,
    settings: Settings,
    package_name: str,
    project_dir: Path,
) -> dict[str, str]:
    """Re-emit ``lib/generated/*_layout.dart`` from the current compiler."""
    from figma_flutter_agent.generator.layout import render_layout_file
    from figma_flutter_agent.generator.normalize import normalize_clean_tree

    uses_svg = any("flutter_svg" in content for content in planned.values())
    root = normalize_clean_tree(
        clean_tree,
        use_geometry_planner=True,
        apply_render_safety=False,
        project_dir=project_dir,
    )
    layout_files = render_layout_file(
        root,
        feature_name=feature_name,
        uses_svg=uses_svg,
        package_name=package_name,
        responsive_enabled=settings.agent.responsive.enabled,
        snap_device_pixels=settings.agent.layout.snap_device_pixels,
        use_geometry_planner=True,
    )
    updated = dict(planned)
    updated.update(layout_files)
    return updated


def _planned_with_capture_test(
    planned: dict[str, str],
    *,
    feature_name: str,
    package_name: str,
    settings: Settings,
    clean_tree: CleanDesignTreeNode | None,
) -> dict[str, str]:
    from figma_flutter_agent.validation.golden_capture.capture_host import (
        _visual_refine_fast_capture,
    )

    architecture = settings.agent.flutter.architecture
    screen_class = detect_screen_class_from_planned_files(
        planned,
        feature_name=feature_name,
        architecture=architecture,
    )
    from figma_flutter_agent.generator.render_surface import resolve_capture_surface_size

    artboard_width, artboard_height = artboard_size(clean_tree)
    surface_width, surface_height = resolve_capture_surface_size(
        artboard_width=artboard_width,
        artboard_height=artboard_height,
    )
    renderer = DartRenderer()
    generation_cfg = settings.agent.generation
    collect_keys = (
        generation_cfg.runtime_geometry_gate or generation_cfg.runtime_geometry_capture_if_missing
    )
    common = {
        "feature_name": feature_name,
        "screen_class": screen_class,
        "package_name": package_name,
        "surface_width": surface_width,
        "surface_height": surface_height,
        "max_web_width": settings.agent.responsive.max_web_width,
    }
    updated = dict(planned)
    use_fast_capture = _visual_refine_fast_capture(settings)
    if use_fast_capture or not settings.agent.validation.generate_golden_test:
        updated.update(
            renderer.render_capture_test(
                **common,
                collect_figma_keys=collect_keys,
            )
        )
    if settings.agent.validation.generate_golden_test:
        updated.update(renderer.render_golden_test(**common))
    return updated


def planned_for_capture_from_map(
    project_dir: Path,
    *,
    feature_name: str,
    planned_files: dict[str, str],
    settings: Settings,
    clean_tree: CleanDesignTreeNode | None,
    layout_refresh: bool = False,
) -> CapturePlanResult:
    """Build planned files plus a capture test from a pipeline planned map."""
    package_name = read_pubspec_name(project_dir)
    planned = dict(planned_files)
    refreshed = layout_refresh and clean_tree is not None
    if refreshed:
        assert clean_tree is not None
        planned = refresh_planned_layout_from_clean_tree(
            planned,
            feature_name=feature_name,
            clean_tree=clean_tree,
            settings=settings,
            package_name=package_name,
            project_dir=project_dir,
        )
    planned = _planned_with_capture_test(
        planned,
        feature_name=feature_name,
        package_name=package_name,
        settings=settings,
        clean_tree=clean_tree,
    )
    layout_hash, screen_hash = planned_file_hashes(planned, feature_name)
    return CapturePlanResult(
        planned=planned,
        source_mode=(REFRESHED_CLEAN_TREE_SOURCE_MODE if refreshed else EXACT_BUNDLE_SOURCE_MODE),
        target_source="pipeline_planned",
        layout_hash=layout_hash,
        screen_hash=screen_hash,
    )


def planned_for_capture(
    project_dir: Path,
    *,
    feature_name: str,
    bundle_path: Path,
    settings: Settings,
    clean_tree: CleanDesignTreeNode | None,
    layout_refresh: bool = False,
) -> CapturePlanResult:
    """Build planned files plus a capture test from a cached Dart bundle."""
    package_name = read_pubspec_name(project_dir)
    bundle_text = bundle_path.read_text(encoding="utf-8")
    planned = planned_files_from_dart_bundle(bundle_text, package_name=package_name)
    refreshed = layout_refresh and clean_tree is not None
    if refreshed:
        assert clean_tree is not None
        planned = refresh_planned_layout_from_clean_tree(
            planned,
            feature_name=feature_name,
            clean_tree=clean_tree,
            settings=settings,
            package_name=package_name,
            project_dir=project_dir,
        )
    planned = _planned_with_capture_test(
        planned,
        feature_name=feature_name,
        package_name=package_name,
        settings=settings,
        clean_tree=clean_tree,
    )
    layout_hash, screen_hash = planned_file_hashes(planned, feature_name)
    return CapturePlanResult(
        planned=planned,
        source_mode=(REFRESHED_CLEAN_TREE_SOURCE_MODE if refreshed else EXACT_BUNDLE_SOURCE_MODE),
        target_source="debug_bundle",
        bundle_path=bundle_path.as_posix(),
        bundle_hash=sha256_text(bundle_text),
        layout_hash=layout_hash,
        screen_hash=screen_hash,
    )
