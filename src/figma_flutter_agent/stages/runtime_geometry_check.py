"""Runtime geometry gate: golden figma_keys vs Figma stack placements."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.geometry_metrics import GeometryTierThresholds
from figma_flutter_agent.validation.golden_capture import (
    capture_planned_for_fixture,
    golden_figma_keys_relative_path,
    persist_golden_capture_timings,
)
from figma_flutter_agent.validation.runtime_geometry import (
    compare_runtime_to_figma,
    geometry_feedback_from_mapper_payload,
    load_runtime_bounds_json,
)


def _project_figma_keys_path(project_dir: Path, feature_name: str) -> Path:
    return project_dir / golden_figma_keys_relative_path(feature_name)


def _load_mapper_payload(
    project_dir: Path | None,
    feature_name: str,
) -> dict[str, object] | None:
    if project_dir is None:
        return None
    keys_path = _project_figma_keys_path(project_dir, feature_name)
    if not keys_path.is_file():
        return None
    raw = keys_path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else None


def evaluate_runtime_geometry(
    *,
    clean_tree: CleanDesignTreeNode,
    planned_files: dict[str, str],
    feature_name: str,
    project_dir: Path | None,
    settings,
    min_iou: float,
    tier_thresholds: GeometryTierThresholds,
    use_tier_thresholds: bool,
    capture_if_missing: bool,
) -> tuple[list[str], str]:
    """Return analyzer-style error lines and LLM feedback for geometry mismatches."""
    mapper_payload = _load_mapper_payload(project_dir, feature_name)
    if mapper_payload is None and capture_if_missing:
        log = logger.bind(stage="runtime_geometry", feature_name=feature_name)
        log.info(
            "No {} on disk; capturing golden for runtime geometry check",
            golden_figma_keys_relative_path(feature_name),
        )
        capture = capture_planned_for_fixture(
            None,
            planned_files,
            feature_name=feature_name,
            layout_tree=clean_tree,
            settings=settings,
            project_dir=project_dir,
            flutter_sdk=settings.flutter_sdk or None,
        )
        if capture.timings is not None:
            persist_golden_capture_timings(
                capture.timings,
                project_dir=project_dir,
            )
        if capture.ok and capture.figma_key_rects:
            mapper_payload = capture.figma_key_rects
        elif not capture.ok:
            log.warning("Runtime geometry capture skipped: {}", capture.reason)

    if not mapper_payload:
        return [], ""

    feedback = geometry_feedback_from_mapper_payload(
        clean_tree,
        mapper_payload,
        min_iou=min_iou,
        tier_thresholds=tier_thresholds,
        use_tier_thresholds=use_tier_thresholds,
    )
    if not feedback:
        return [], ""

    bounds = load_runtime_bounds_json(
        json.dumps(mapper_payload, ensure_ascii=False).encode("utf-8"),
    )
    from figma_flutter_agent.generator.subtree import (
        _should_insert_missing_subtree,
        collect_subtree_widget_specs,
    )
    from figma_flutter_agent.validation.runtime_geometry import (
        collect_interactive_placement_ids,
    )

    node_ids = collect_interactive_placement_ids(clean_tree)
    for spec in collect_subtree_widget_specs(clean_tree, widget_suffix="Widget"):
        if _should_insert_missing_subtree(spec) and spec.node_id not in node_ids:
            node_ids.append(spec.node_id)
    mismatches = compare_runtime_to_figma(
        clean_tree,
        bounds,
        node_ids=node_ids,
        min_iou=min_iou,
        tier_thresholds=tier_thresholds,
        use_tier_thresholds=use_tier_thresholds,
    )
    errors = [item.format_feedback_line() for item in mismatches]
    return errors, feedback


def evaluate_runtime_geometry_for_repair(
    request,
    planned_files: dict[str, str],
) -> tuple[list[str], str]:
    """Geometry gate driven by ``agent.generation`` settings."""
    generation_cfg = request.settings.agent.generation
    if not generation_cfg.runtime_geometry_gate:
        return [], ""
    return evaluate_runtime_geometry(
        clean_tree=request.clean_tree,
        planned_files=planned_files,
        feature_name=request.resolved_feature,
        project_dir=request.project_dir,
        settings=request.settings,
        min_iou=generation_cfg.runtime_geometry_min_iou,
        tier_thresholds=generation_cfg.geometry_tier_thresholds(),
        use_tier_thresholds=generation_cfg.runtime_geometry_use_tier_thresholds,
        capture_if_missing=generation_cfg.runtime_geometry_capture_if_missing,
    )
