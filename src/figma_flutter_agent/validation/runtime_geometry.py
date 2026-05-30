"""Compare golden runtime bounds (figma keys JSON) against Figma design placements."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.schemas import CleanDesignTreeNode, StackPlacement
from figma_flutter_agent.validation.figma_keys import figma_id_from_key_token
from figma_flutter_agent.validation.geometry_metrics import (
    GeometryTierThresholds,
    box_metrics,
    build_parent_map,
    geometry_tier_for_node,
    node_depth,
    passes_geometry_threshold,
)


@dataclass(frozen=True)
class RuntimeBounds:
    """Axis-aligned box in design-space logical pixels."""

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height


@dataclass(frozen=True)
class GeometryMismatch:
    """One widget whose runtime box diverges from the clean-tree placement."""

    figma_id: str
    iou: float
    giou: float
    diou: float
    expected: RuntimeBounds
    runtime: RuntimeBounds | None
    delta_left: float
    delta_top: float
    missing: bool
    center_delta_x: float = 0.0
    center_delta_y: float = 0.0
    tier: str = "component"
    min_giou: float = 0.95

    def format_feedback_line(self) -> str:
        if self.missing or self.runtime is None:
            return (
                f"ERROR: Widget figma_id {self.figma_id!r} is missing on screen "
                f"(GIoU = 0, tier {self.tier}, required >= {self.min_giou:.2f}). "
                f"Expected position: left {self.expected.left:.1f}, top {self.expected.top:.1f}, "
                f"size {self.expected.width:.1f}x{self.expected.height:.1f}. "
                "Ensure the node is present in screenIr and rendered with a figma ValueKey."
            )
        shift_h = "right" if self.delta_left > 0 else "left"
        shift_v = "down" if self.delta_top > 0 else "up"
        center_h = "right" if self.center_delta_x > 0 else "left"
        center_v = "down" if self.center_delta_y > 0 else "up"
        return (
            f"ERROR: Widget figma_id {self.figma_id!r} "
            f"(tier {self.tier}, required GIoU >= {self.min_giou:.2f}): "
            f"IoU = {self.iou:.2f}, GIoU = {self.giou:.2f}, DIoU = {self.diou:.2f}. "
            f"Expected: left {self.expected.left:.1f}, top {self.expected.top:.1f}. "
            f"Runtime: left {self.runtime.left:.1f}, top {self.runtime.top:.1f}. "
            f"Corner shift {abs(self.delta_left):.0f}px {shift_h}, "
            f"{abs(self.delta_top):.0f}px {shift_v}; "
            f"center bias {abs(self.center_delta_x):.0f}px {center_h}, "
            f"{abs(self.center_delta_y):.0f}px {center_v}. Correct layout parameters."
        )


def load_runtime_bounds_json(source: Path | str | bytes) -> dict[str, RuntimeBounds]:
    """Parse ``*_figma_keys.json`` written by the golden harness."""
    if isinstance(source, Path):
        raw_text = source.read_text(encoding="utf-8")
    elif isinstance(source, bytes):
        raw_text = source.decode("utf-8")
    else:
        raw_text = source
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        msg = "figma_keys JSON must be an object"
        raise ValueError(msg)
    bounds: dict[str, RuntimeBounds] = {}
    for token, value in payload.items():
        if not isinstance(value, dict):
            continue
        left = float(value.get("left", 0))
        top = float(value.get("top", 0))
        width = float(value.get("width", 0))
        height = float(value.get("height", 0))
        if width <= 0 or height <= 0:
            continue
        node_id = figma_id_from_key_token(str(token))
        bounds[node_id] = RuntimeBounds(left=left, top=top, width=width, height=height)
    return bounds


def expected_bounds_from_placement(placement: StackPlacement) -> RuntimeBounds | None:
    width = placement.width
    height = placement.height
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    return RuntimeBounds(
        left=float(placement.left),
        top=float(placement.top),
        width=float(width),
        height=float(height),
    )


def _bounds_tuple(bounds: RuntimeBounds) -> tuple[float, float, float, float]:
    return bounds.left, bounds.top, bounds.width, bounds.height


def placement_iou(expected: RuntimeBounds, runtime: RuntimeBounds) -> float:
    return box_metrics(_bounds_tuple(expected), _bounds_tuple(runtime)).iou


def compare_runtime_to_figma(
    clean_tree: CleanDesignTreeNode,
    runtime_bounds: dict[str, RuntimeBounds],
    *,
    node_ids: list[str] | None = None,
    min_iou: float | None = None,
    tier_thresholds: GeometryTierThresholds | None = None,
    use_tier_thresholds: bool = True,
) -> list[GeometryMismatch]:
    """Return mismatches where runtime GIoU is below the tier (or flat) threshold."""
    from figma_flutter_agent.generator.ir_tree import index_clean_tree

    thresholds = tier_thresholds or GeometryTierThresholds()
    tree_by_id = index_clean_tree(clean_tree)
    parents = build_parent_map(clean_tree)
    targets = node_ids if node_ids is not None else list(tree_by_id)
    mismatches: list[GeometryMismatch] = []
    for figma_id in targets:
        clean = tree_by_id.get(figma_id)
        if clean is None or clean.stack_placement is None:
            continue
        expected = expected_bounds_from_placement(clean.stack_placement)
        if expected is None:
            continue
        depth = node_depth(figma_id, parent_by_id=parents)
        tier = geometry_tier_for_node(clean, root_id=clean_tree.id, depth=depth)
        if use_tier_thresholds:
            min_giou = thresholds.threshold_for_tier(tier)
        else:
            min_giou = min_iou if min_iou is not None else thresholds.structural
        runtime = runtime_bounds.get(figma_id)
        if runtime is None:
            mismatches.append(
                GeometryMismatch(
                    figma_id=figma_id,
                    iou=0.0,
                    giou=0.0,
                    diou=-1.0,
                    expected=expected,
                    runtime=None,
                    delta_left=0.0,
                    delta_top=0.0,
                    missing=True,
                    tier=tier,
                    min_giou=min_giou,
                )
            )
            continue
        metrics = box_metrics(_bounds_tuple(expected), _bounds_tuple(runtime))
        if passes_geometry_threshold(metrics, min_giou):
            continue
        mismatches.append(
            GeometryMismatch(
                figma_id=figma_id,
                iou=metrics.iou,
                giou=metrics.giou,
                diou=metrics.diou,
                expected=expected,
                runtime=runtime,
                delta_left=runtime.left - expected.left,
                delta_top=runtime.top - expected.top,
                center_delta_x=metrics.center_delta_x,
                center_delta_y=metrics.center_delta_y,
                missing=False,
                tier=tier,
                min_giou=min_giou,
            )
        )
    return mismatches


def format_geometry_feedback(
    mismatches: list[GeometryMismatch],
    *,
    max_lines: int = 12,
) -> str:
    """Build LLM-facing geometry instructions from mismatches."""
    if not mismatches:
        return ""
    lines = [item.format_feedback_line() for item in mismatches[:max_lines]]
    if len(mismatches) > max_lines:
        lines.append(f"... and {len(mismatches) - max_lines} more geometry mismatches.")
    return "\n".join(lines)


def geometry_feedback_from_mapper_payload(
    clean_tree: CleanDesignTreeNode,
    mapper_payload: dict[str, object] | None,
    *,
    min_iou: float | None = None,
    tier_thresholds: GeometryTierThresholds | None = None,
    use_tier_thresholds: bool = True,
    max_lines: int = 12,
) -> str:
    """Build LLM geometry hints from golden ``figma_keys`` JSON."""
    if not mapper_payload:
        return ""
    bounds = load_runtime_bounds_json(
        json.dumps(mapper_payload, ensure_ascii=False).encode("utf-8")
    )
    node_ids = collect_interactive_placement_ids(clean_tree)
    from figma_flutter_agent.generator.subtree_widgets import collect_subtree_widget_specs

    for spec in collect_subtree_widget_specs(clean_tree, widget_suffix="Widget"):
        from figma_flutter_agent.generator.subtree_widgets import _should_insert_missing_subtree

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
    return format_geometry_feedback(mismatches, max_lines=max_lines)


def collect_interactive_placement_ids(root: CleanDesignTreeNode) -> list[str]:
    """Figma ids for buttons/inputs and other nodes with explicit stack placement."""
    from figma_flutter_agent.schemas import NodeType

    interactive = {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.TEXT,
    }
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if node.stack_placement is not None and node.type in interactive:
            ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


__all__ = [
    "GeometryMismatch",
    "GeometryTierThresholds",
    "RuntimeBounds",
    "collect_interactive_placement_ids",
    "compare_runtime_to_figma",
    "expected_bounds_from_placement",
    "format_geometry_feedback",
    "geometry_feedback_from_mapper_payload",
    "load_runtime_bounds_json",
    "placement_iou",
]
