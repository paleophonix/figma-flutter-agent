"""Wizard view capture: Figma reference, Flutter golden, diff → flat ``.debug/<project>/<feature>/``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.capture import (
    DebugCaptureOutcome,
    persist_latest_screen_capture,
)
from figma_flutter_agent.debug.paths import debug_capture_artifact_path, screen_capture_dir
from figma_flutter_agent.dev.run import plan_run_screen
from figma_flutter_agent.dev.view_capture_timeout import capture_settings_for_planned
from figma_flutter_agent.dev.view_render_models import ViewRendersResult
from figma_flutter_agent.dev.view_render_plan import (
    MIXED_SOURCE_ORACLE_WARNING,
    CapturePlanResult,
    load_clean_tree_from_debug,
    oracle_visual_repair_eligible,
    planned_for_capture,
)
from figma_flutter_agent.dev.warm_capture import capture_planned_in_warm_sandbox
from figma_flutter_agent.errors import FastPreviewUnavailableError, FlutterProjectError
from figma_flutter_agent.preview import (
    PreviewCaptureRequest,
    capture_preview_png,
    preview_scene_from_clean_tree,
)
from figma_flutter_agent.preview.modes import CaptureBackend
from figma_flutter_agent.validation.compare import compare_png_bytes
from figma_flutter_agent.validation.pixel.coordinates import parse_flutter_mapper_payload
from figma_flutter_agent.validation.pixel.heatmap import render_visual_diff_heatmap_png
from figma_flutter_agent.validation.pixel.models import (
    VisualCompareResult,
)
from figma_flutter_agent.validation.reference import (
    export_figma_reference,
    load_cached_reference_png,
)

# First warm ``flutter test`` compile on Windows can exceed 8 min; wizard allows up to 20 min.


def _load_figma_root_from_dump(dump_path: Path) -> dict[str, Any]:
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "id" in payload:
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("document"), dict):
        document = payload["document"]
        if isinstance(document, dict):
            return document
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
    from figma_flutter_agent.figma.client import FigmaConnector

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


def _capture_outcome_from_plan(
    capture_plan: CapturePlanResult,
    *,
    capture_dir: Path,
    figma_reference_ok: bool,
    flutter_capture_ok: bool,
    diff_ok: bool,
    changed_ratio: float | None,
    warnings: tuple[str, ...],
) -> DebugCaptureOutcome:
    repair_eligible = oracle_visual_repair_eligible(capture_plan.source_mode)
    merged_warnings = warnings
    if not repair_eligible and MIXED_SOURCE_ORACLE_WARNING not in warnings:
        merged_warnings = warnings + (MIXED_SOURCE_ORACLE_WARNING,)
    return DebugCaptureOutcome(
        capture_dir=capture_dir,
        figma_reference_ok=figma_reference_ok,
        flutter_capture_ok=flutter_capture_ok,
        diff_ok=diff_ok and repair_eligible,
        changed_ratio=changed_ratio if repair_eligible else None,
        warnings=merged_warnings,
        source_mode=capture_plan.source_mode,
        target_source=capture_plan.target_source,
        bundle_path=capture_plan.bundle_path,
        bundle_hash=capture_plan.bundle_hash,
        layout_hash=capture_plan.layout_hash,
        screen_hash=capture_plan.screen_hash,
        visual_repair_eligible=repair_eligible,
    )


def _capture_flutter_render_png(
    project_dir: Path,
    *,
    feature_name: str,
    bundle_path: Path,
    settings: Settings,
) -> tuple[bytes, CapturePlanResult]:
    clean_tree = load_clean_tree_from_debug(project_dir, feature_name)
    capture_plan = planned_for_capture(
        project_dir,
        feature_name=feature_name,
        bundle_path=bundle_path,
        settings=settings,
        clean_tree=clean_tree,
    )
    capture_settings = capture_settings_for_planned(settings, capture_plan.planned)
    capture = capture_planned_in_warm_sandbox(
        capture_plan.planned,
        feature_name=feature_name,
        project_dir=project_dir,
        layout_tree=clean_tree,
        settings=capture_settings,
    )
    if not capture.ok or capture.png is None:
        reason = capture.reason or "golden capture failed"
        raise FlutterProjectError(reason)
    return capture.png, capture_plan


def run_view_preview_capture(
    project_dir: Path,
    *,
    feature_name: str,
    bundle_path: Path,
    settings: Settings,
) -> Path:
    """Capture a fast browser preview PNG without Flutter test tooling.

    Args:
        project_dir: Flutter project root.
        feature_name: Active screen feature slug.
        bundle_path: Cached ``.debug`` Dart bundle (unused; kept for wizard API stability).
        settings: Agent settings (preview timeout).

    Returns:
        Path to ``.debug/<project>/<feature>/preview_capture.png``.

    Raises:
        FlutterProjectError: When browser preview capture fails.
        FastPreviewUnavailableError: When the browser backend is unavailable.
    """
    _ = bundle_path
    try:
        clean_tree = load_clean_tree_from_debug(project_dir, feature_name)
        scene = preview_scene_from_clean_tree(clean_tree)
        output_path = debug_capture_artifact_path(
            project_dir,
            feature_name,
            "preview_capture",
        )
        result = capture_preview_png(
            PreviewCaptureRequest(
                scene=scene,
                output_path=output_path,
                timeout_sec=settings.agent.generation.golden_capture_timeout_sec,
                screen_id=feature_name,
            ),
        )
        if not result.ok or result.png is None:
            reason = result.reason or "browser preview capture failed"
            raise FlutterProjectError(reason)
        png = result.png
        _ = result.backend or CaptureBackend.BROWSER_PREVIEW.value
        outcome = DebugCaptureOutcome(
            capture_dir=screen_capture_dir(project_dir, feature_name),
            figma_reference_ok=False,
            flutter_capture_ok=True,
            diff_ok=False,
            changed_ratio=None,
            warnings=(),
        )
        persist_latest_screen_capture(
            project_dir,
            feature_name,
            capture_png=png,
            use_preview_artifact=True,
            outcome=outcome,
        )
        return output_path
    except (FlutterProjectError, FastPreviewUnavailableError):
        raise


def run_view_oracle_capture(
    project_dir: Path,
    *,
    feature_name: str,
    bundle_path: Path,
    settings: Settings,
) -> Path:
    """Capture a blocking oracle Flutter render PNG for wizard view (no pixel diff).

    Args:
        project_dir: Flutter project root.
        feature_name: Active screen feature slug.
        bundle_path: Cached ``.debug`` Dart bundle for warm-sandbox capture.
        settings: Agent settings (golden runtime, capture timeout).

    Returns:
        Path to ``.debug/<project>/<feature>/capture.png``.

    Raises:
        FlutterProjectError: When golden capture fails.
    """
    png, capture_plan = _capture_flutter_render_png(
        project_dir,
        feature_name=feature_name,
        bundle_path=bundle_path,
        settings=settings,
    )
    outcome = _capture_outcome_from_plan(
        capture_plan,
        capture_dir=screen_capture_dir(project_dir, feature_name),
        figma_reference_ok=False,
        flutter_capture_ok=True,
        diff_ok=False,
        changed_ratio=None,
        warnings=(),
    )
    persist_latest_screen_capture(
        project_dir,
        feature_name,
        capture_png=png,
        outcome=outcome,
    )
    return debug_capture_artifact_path(project_dir, feature_name, "capture")


async def run_view_combat_renders(
    project_dir: Path,
    *,
    feature_name: str,
    bundle_path: Path,
    settings: Settings,
) -> ViewRendersResult:
    """Capture Figma reference, Flutter render, and diff heatmap (flat, latest-only).

    Args:
        project_dir: Flutter project root.
        feature_name: Active screen feature slug.
        bundle_path: Cached ``.debug`` Dart bundle (read in-memory; not written to the app tree).
        settings: Agent settings (golden runtime, reference scale, thresholds).

    Returns:
        Paths and metrics for the latest flat capture artifacts.

    Raises:
        FlutterProjectError: When the bundle cannot be deployed or capture fails fatally.
    """
    warnings: list[str] = []
    screen_dir = screen_capture_dir(project_dir, feature_name)
    try:
        clean_tree = load_clean_tree_from_debug(project_dir, feature_name)
        figma_png = await _resolve_figma_reference_png(
            project_dir=project_dir,
            feature_name=feature_name,
            settings=settings,
        )
        figma_ok = figma_png is not None
        if figma_png is None:
            message = (
                f"No Figma reference for {feature_name!r} "
                f"(set FIGMA_ACCESS_TOKEN or export to .debug/reference/figma/)"
            )
            warnings.append(message)
            logger.warning(message)

        planned = planned_for_capture(
            project_dir,
            feature_name=feature_name,
            bundle_path=bundle_path,
            settings=settings,
            clean_tree=clean_tree,
        )
        capture_settings = capture_settings_for_planned(settings, planned.planned)
        capture = capture_planned_in_warm_sandbox(
            planned.planned,
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
            logger.error("Flutter render capture failed: {}", reason)
            outcome = _capture_outcome_from_plan(
                planned,
                capture_dir=screen_dir,
                figma_reference_ok=figma_ok,
                flutter_capture_ok=False,
                diff_ok=False,
                changed_ratio=None,
                warnings=tuple(warnings),
            )
            persist_latest_screen_capture(
                project_dir,
                feature_name,
                outcome=outcome,
            )
            return ViewRendersResult(
                render_dir=screen_dir,
                figma_reference_ok=figma_ok,
                flutter_capture_ok=False,
                diff_ok=False,
                changed_ratio=None,
                warnings=tuple(warnings),
            )

        assert flutter_png is not None
        heatmap_png: bytes | None = None
        diff_ok = False

        if not figma_ok:
            outcome = _capture_outcome_from_plan(
                planned,
                capture_dir=screen_dir,
                figma_reference_ok=False,
                flutter_capture_ok=True,
                diff_ok=False,
                changed_ratio=None,
                warnings=tuple(warnings),
            )
            persist_latest_screen_capture(
                project_dir,
                feature_name,
                capture_png=flutter_png,
                outcome=outcome,
            )
            return ViewRendersResult(
                render_dir=screen_dir,
                figma_reference_ok=False,
                flutter_capture_ok=True,
                diff_ok=False,
                changed_ratio=None,
                warnings=tuple(warnings),
            )

        assert figma_png is not None
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
        diff_ok = True

        outcome = _capture_outcome_from_plan(
            planned,
            capture_dir=screen_dir,
            figma_reference_ok=True,
            flutter_capture_ok=True,
            diff_ok=diff_ok,
            changed_ratio=changed_ratio,
            warnings=tuple(warnings),
        )
        persist_latest_screen_capture(
            project_dir,
            feature_name,
            capture_png=flutter_png,
            diff_heatmap_png=heatmap_png,
            outcome=outcome,
        )
        logger.info(
            "View combat capture for {}: {:.2%} changed vs Figma → {}",
            feature_name,
            changed_ratio,
            debug_capture_artifact_path(project_dir, feature_name, "capture").as_posix(),
        )
        return ViewRendersResult(
            render_dir=screen_dir,
            figma_reference_ok=True,
            flutter_capture_ok=True,
            diff_ok=outcome.diff_ok,
            changed_ratio=outcome.changed_ratio,
            warnings=outcome.warnings,
        )
    except FlutterProjectError:
        raise
