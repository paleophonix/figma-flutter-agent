"""Runtime geometry gate for offline fixture golden captures."""

from __future__ import annotations

import json
from dataclasses import dataclass

from figma_flutter_agent.config import Settings
from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.fixtures.screens_manifest import (
    ScreenFixtureEntry,
    load_layout_tree,
    load_screens_manifest,
)
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files
from figma_flutter_agent.generator.subtree_widgets import (
    _should_insert_missing_subtree,
    collect_subtree_widget_specs,
)
from figma_flutter_agent.validation.golden_runtime import resolve_golden_runtime
from figma_flutter_agent.validation.runtime_geometry import (
    collect_interactive_placement_ids,
    compare_runtime_to_figma,
    format_geometry_feedback,
    geometry_feedback_from_mapper_payload,
    load_runtime_bounds_json,
)


@dataclass(frozen=True)
class FixtureGeometryResult:
    """Outcome of runtime geometry verification for one fixture screen."""

    screen_id: str
    ok: bool
    skipped: bool = False
    reason: str | None = None
    mismatch_count: int = 0
    feedback: str = ""


def check_fixture_geometry(
    entry: ScreenFixtureEntry,
    *,
    settings: Settings | None = None,
    min_iou: float | None = None,
    golden_runtime: str | None = None,
    flutter_sdk: str | None = None,
) -> FixtureGeometryResult:
    """Capture golden figma_keys and compare runtime bounds to layout placements."""
    resolved = settings or Settings()
    generation = resolved.agent.generation
    flat_threshold = min_iou if min_iou is not None else generation.runtime_geometry_min_iou
    tier_thresholds = generation.geometry_tier_thresholds()
    use_tiers = generation.runtime_geometry_use_tier_thresholds

    runtime = golden_runtime
    if runtime is None:
        runtime = resolve_golden_runtime(settings=resolved).runtime
    sdk = flutter_sdk if flutter_sdk is not None else resolved.flutter_sdk or None

    from figma_flutter_agent.validation.golden_capture import capture_planned_flutter_golden_png

    tree = load_layout_tree(entry)
    planned = reconcile_planned_dart_files(build_fixture_planned_files(entry))
    capture = capture_planned_flutter_golden_png(
        planned,
        feature_name=entry.feature,
        settings=resolved,
        golden_runtime=runtime,
        flutter_sdk=sdk,
        layout_tree=tree,
    )
    if not capture.ok:
        return FixtureGeometryResult(
            screen_id=entry.id,
            ok=False,
            skipped=True,
            reason=capture.reason or "golden capture failed",
        )
    if not capture.figma_key_rects:
        return FixtureGeometryResult(
            screen_id=entry.id,
            ok=False,
            skipped=True,
            reason="capture did not emit figma_keys JSON",
        )

    feedback = geometry_feedback_from_mapper_payload(
        tree,
        capture.figma_key_rects,
        min_iou=flat_threshold,
        tier_thresholds=tier_thresholds,
        use_tier_thresholds=use_tiers,
    )
    if not feedback:
        return FixtureGeometryResult(screen_id=entry.id, ok=True)

    bounds = load_runtime_bounds_json(
        json.dumps(capture.figma_key_rects, ensure_ascii=False).encode("utf-8"),
    )
    node_ids = collect_interactive_placement_ids(tree)
    for spec in collect_subtree_widget_specs(tree, widget_suffix="Widget"):
        if _should_insert_missing_subtree(spec) and spec.node_id not in node_ids:
            node_ids.append(spec.node_id)
    mismatches = compare_runtime_to_figma(
        tree,
        bounds,
        node_ids=node_ids,
        min_iou=flat_threshold,
        tier_thresholds=tier_thresholds,
        use_tier_thresholds=use_tiers,
    )
    gate_label = "tier GIoU" if use_tiers else f"GIoU {flat_threshold:.2f}"
    return FixtureGeometryResult(
        screen_id=entry.id,
        ok=False,
        mismatch_count=len(mismatches),
        feedback=format_geometry_feedback(mismatches),
        reason=f"{len(mismatches)} widget(s) below {gate_label}",
    )


def check_all_fixture_geometry(
    *,
    screen_ids: list[str] | None = None,
    settings: Settings | None = None,
    min_iou: float | None = None,
    golden_runtime: str | None = None,
) -> list[FixtureGeometryResult]:
    """Run geometry gate for manifest screens (captures fresh goldens each time)."""
    manifest = load_screens_manifest()
    entries = manifest.screens
    if screen_ids is not None:
        wanted = frozenset(screen_ids)
        entries = [entry for entry in entries if entry.id in wanted]
    resolved = settings or Settings()
    sdk = resolved.flutter_sdk or None
    return [
        check_fixture_geometry(
            entry,
            settings=resolved,
            min_iou=min_iou,
            golden_runtime=golden_runtime,
            flutter_sdk=sdk,
        )
        for entry in entries
    ]
