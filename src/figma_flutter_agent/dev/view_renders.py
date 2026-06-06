"""Wizard view combat renders: Figma reference, Flutter golden, diff → ``logs/renders/``."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.dart_bundle import (
    detect_screen_class_from_planned_files,
    planned_files_from_dart_bundle,
)
from figma_flutter_agent.dev.run import plan_run_screen
from figma_flutter_agent.dev.warm_capture import capture_planned_in_warm_sandbox
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.generator.pubspec import read_pubspec_name
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.observability import new_run_id
from figma_flutter_agent.render_log import (
    bind_render_log_session,
    clear_render_log_session,
    record_render_capture_failure,
    record_render_png,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.compare import compare_png_bytes
from figma_flutter_agent.validation.pixeldiff import (
    VisualCompareResult,
    parse_flutter_mapper_payload,
    render_visual_diff_heatmap_png,
)
from figma_flutter_agent.tools.ast_sidecar import AST_SIDECAR_MAX_SOURCE_BYTES
from figma_flutter_agent.validation.reference import (
    export_figma_reference,
    load_cached_reference_png,
)

# First warm ``flutter test`` compile on Windows can exceed 8 min; wizard allows up to 20 min.
_VIEW_RENDER_MIN_CAPTURE_TIMEOUT_SEC = 1200.0
_VIEW_RENDER_LARGE_CAPTURE_TIMEOUT_SEC = 1200.0


@dataclass(frozen=True)
class ViewRendersResult:
    """Outcome of a wizard combat-render capture session."""

    render_dir: Path
    figma_reference_ok: bool
    flutter_capture_ok: bool
    diff_ok: bool
    changed_ratio: float | None = None
    warnings: tuple[str, ...] = ()


def load_clean_tree_from_debug(
    project_dir: Path,
    feature_name: str,
) -> CleanDesignTreeNode | None:
    """Load ``cleanTree`` from ``.figma_debug/processed/<feature>_layout.json`` when present."""
    processed = project_dir / ".figma_debug" / "processed" / f"{feature_name}_layout.json"
    if not processed.is_file():
        return None
    payload = json.loads(processed.read_text(encoding="utf-8"))
    tree_payload = payload.get("cleanTree")
    if tree_payload is None:
        return None
    return CleanDesignTreeNode.model_validate(tree_payload)


def _capture_settings_for_planned(
    settings: Settings,
    planned: dict[str, str],
) -> Settings:
    """Raise capture timeout for warm-sandbox ``flutter test`` (first compile can exceed 5 min)."""
    layout_bytes = max(
        (
            len(content.encode("utf-8"))
            for path, content in planned.items()
            if path.replace("\\", "/").startswith("lib/generated/")
            and path.endswith("_layout.dart")
        ),
        default=0,
    )
    base = settings.agent.generation.golden_capture_timeout_sec
    extended = max(base, _VIEW_RENDER_MIN_CAPTURE_TIMEOUT_SEC)
    if layout_bytes > AST_SIDECAR_MAX_SOURCE_BYTES:
        extended = max(extended, _VIEW_RENDER_LARGE_CAPTURE_TIMEOUT_SEC)
    if extended <= base:
        return settings
    if layout_bytes > AST_SIDECAR_MAX_SOURCE_BYTES:
        logger.info(
            "Large generated layout ({} KiB); flutter test capture timeout {:.0f}s",
            layout_bytes // 1024,
            extended,
        )
    else:
        logger.info(
            "Warm sandbox first compile; flutter test capture timeout {:.0f}s",
            extended,
        )
    return settings.model_copy(
        update={
            "agent": settings.agent.model_copy(
                update={
                    "generation": settings.agent.generation.model_copy(
                        update={"golden_capture_timeout_sec": extended},
                    ),
                },
            ),
        },
    )


def _artboard_size(clean_tree: CleanDesignTreeNode | None) -> tuple[int, int]:
    if clean_tree is None:
        return 390, 844
    width = clean_tree.sizing.width
    height = clean_tree.sizing.height
    surface_width = max(int(width), 1) if isinstance(width, (int, float)) and width > 0 else 390
    surface_height = (
        max(int(height), 1) if isinstance(height, (int, float)) and height > 0 else 844
    )
    return surface_width, surface_height


def _load_figma_root_from_dump(dump_path: Path) -> dict[str, Any]:
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "id" in payload:
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("document"), dict):
        return payload["document"]
    msg = f"Unsupported dump shape for Figma reference export: {dump_path.as_posix()}"
    raise FlutterProjectError(msg)


async def _resolve_figma_reference_png(
    *,
    project_dir: Path,
    feature_name: str,
    settings: Settings,
) -> bytes | None:
    cached = load_cached_reference_png(project_dir, feature_name)
    if cached is not None:
        logger.info("Using cached Figma reference PNG for {}", feature_name)
        return cached

    token = settings.figma_token().strip()
    if not token:
        return None

    plan = plan_run_screen(project_dir=project_dir, screen_name=feature_name)
    figma_root = _load_figma_root_from_dump(plan.dump_path)
    from figma_flutter_agent.figma.connector import FigmaConnector

    connector = FigmaConnector(token)
    export = await export_figma_reference(
        connector,
        file_key=plan.manifest.file_key,
        node_id=plan.screen.node_id,
        project_dir=project_dir,
        feature_name=feature_name,
        figma_root=figma_root,
        scale=settings.agent.validation.reference_scale,
    )
    if export is None:
        return None
    return export.image_path.read_bytes()


def refresh_planned_layout_from_clean_tree(
    planned: dict[str, str],
    *,
    feature_name: str,
    clean_tree: CleanDesignTreeNode,
    settings: Settings,
    package_name: str,
    project_dir: Path,
) -> dict[str, str]:
    """Re-emit ``lib/generated/*_layout.dart`` from the current compiler (not stale bundles)."""
    from figma_flutter_agent.generator.layout.renderer import render_layout_file
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


def _planned_for_capture(
    project_dir: Path,
    *,
    feature_name: str,
    bundle_path: Path,
    settings: Settings,
    clean_tree: CleanDesignTreeNode | None,
) -> dict[str, str]:
    package_name = read_pubspec_name(project_dir)
    bundle_text = bundle_path.read_text(encoding="utf-8")
    planned = planned_files_from_dart_bundle(bundle_text, package_name=package_name)
    if clean_tree is not None:
        planned = refresh_planned_layout_from_clean_tree(
            planned,
            feature_name=feature_name,
            clean_tree=clean_tree,
            settings=settings,
            package_name=package_name,
            project_dir=project_dir,
        )
    architecture = settings.agent.flutter.architecture
    screen_class = detect_screen_class_from_planned_files(
        planned,
        feature_name=feature_name,
        architecture=architecture,
    )
    surface_width, surface_height = _artboard_size(clean_tree)
    renderer = DartRenderer()
    planned.update(
        renderer.render_capture_test(
            feature_name=feature_name,
            screen_class=screen_class,
            package_name=package_name,
            surface_width=surface_width,
            surface_height=surface_height,
            max_web_width=settings.agent.responsive.max_web_width,
            collect_figma_keys=False,
        )
    )
    return planned


async def run_view_combat_renders(
    project_dir: Path,
    *,
    feature_name: str,
    bundle_path: Path,
    settings: Settings,
) -> ViewRendersResult:
    """Capture Figma reference, Flutter render, and diff heatmap under ``logs/renders/``.

    Args:
        project_dir: Flutter project root.
        feature_name: Active screen feature slug.
        bundle_path: Cached ``.figma_debug`` Dart bundle (read in-memory; not written to the app tree).
        settings: Agent settings (golden runtime, reference scale, thresholds).

    Returns:
        Paths and metrics for the combat render session.

    Raises:
        FlutterProjectError: When the bundle cannot be deployed or capture fails fatally.
    """
    warnings: list[str] = []
    render_dir = bind_render_log_session(
        run_id=new_run_id(),
        feature_name=feature_name,
        project_dir=project_dir,
    )
    try:
        clean_tree = load_clean_tree_from_debug(project_dir, feature_name)
        figma_png = await _resolve_figma_reference_png(
            project_dir=project_dir,
            feature_name=feature_name,
            settings=settings,
        )
        figma_ok = figma_png is not None
        if figma_ok:
            record_render_png("figma_reference", figma_png)
        else:
            message = (
                f"No Figma reference for {feature_name!r} "
                f"(set FIGMA_ACCESS_TOKEN or export to .figma-flutter/reference/)"
            )
            warnings.append(message)
            record_render_capture_failure("figma_reference", message)
            logger.warning(message)

        planned = _planned_for_capture(
            project_dir,
            feature_name=feature_name,
            bundle_path=bundle_path,
            settings=settings,
            clean_tree=clean_tree,
        )
        capture_settings = _capture_settings_for_planned(settings, planned)
        capture = capture_planned_in_warm_sandbox(
            planned,
            feature_name=feature_name,
            project_dir=project_dir,
            layout_tree=clean_tree,
            settings=capture_settings,
        )
        flutter_ok = capture.ok and capture.png is not None
        flutter_png = capture.png
        changed_ratio: float | None = None

        if not flutter_ok:
            reason = capture.reason or "golden capture failed"
            warnings.append(reason)
            record_render_capture_failure("flutter_render", reason)
            logger.error("Flutter render capture failed: {}", reason)
            return ViewRendersResult(
                render_dir=render_dir,
                figma_reference_ok=figma_ok,
                flutter_capture_ok=False,
                diff_ok=False,
                changed_ratio=None,
                warnings=tuple(warnings),
            )

        assert flutter_png is not None
        record_render_png(
            "flutter_render",
            flutter_png,
            extra={"featureName": feature_name, "source": "wizard_view"},
        )

        if not figma_ok:
            return ViewRendersResult(
                render_dir=render_dir,
                figma_reference_ok=False,
                flutter_capture_ok=True,
                diff_ok=False,
                changed_ratio=None,
                warnings=tuple(warnings),
            )

        generation_cfg = settings.agent.generation
        compare_outcome = compare_png_bytes(
            figma_png,
            flutter_png,
            threshold=generation_cfg.llm_visual_refine_threshold,
            clean_tree=clean_tree,
            flutter_mapper=parse_flutter_mapper_payload(capture.figma_key_rects),
            text_coordinate_tolerance=generation_cfg.text_coordinate_tolerance,
        )
        if isinstance(compare_outcome, VisualCompareResult):
            changed_ratio = compare_outcome.pixel.changed_ratio
        else:
            changed_ratio = compare_outcome.changed_ratio

        heatmap_png = render_visual_diff_heatmap_png(
            figma_png,
            flutter_png,
            clean_tree=clean_tree,
        )
        record_render_png(
            "diff_heatmap",
            heatmap_png,
            changed_ratio=changed_ratio,
        )
        logger.info(
            "View combat renders for {}: {:.2%} changed vs Figma → {}",
            feature_name,
            changed_ratio,
            render_dir.resolve().as_posix(),
        )
        return ViewRendersResult(
            render_dir=render_dir,
            figma_reference_ok=True,
            flutter_capture_ok=True,
            diff_ok=True,
            changed_ratio=changed_ratio,
            warnings=tuple(warnings),
        )
    finally:
        clear_render_log_session()
