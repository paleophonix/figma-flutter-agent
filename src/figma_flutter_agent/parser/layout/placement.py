"""Stack placement extraction and reconciliation helpers."""

from __future__ import annotations

from typing import Any, Literal, cast

from figma_flutter_agent.parser.numeric_rounding import (
    round_geometry,
    round_stack_placement,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    HorizontalConstraint,
    NodeStyle,
    NodeType,
    SizingMode,
    StackPlacement,
    VerticalConstraint,
)

from .sizing import _constraint_axis

_BOTTOM_ANCHORED_MAX_MARGIN_PX = 150.0
_BOTTOM_ANCHORED_MIN_TOP_DELTA_PX = 20.0


def extract_stack_placement(
    node: dict[str, Any],
    parent: dict[str, Any],
) -> StackPlacement | None:
    """Extract classic frame constraints and edge distances for Stack children."""
    parent_mode = parent.get("layoutMode")
    is_classic_stack = parent_mode in (None, "NONE")
    is_auto_absolute = node.get("layoutPositioning") == "ABSOLUTE"
    if not is_classic_stack and not is_auto_absolute:
        return None

    node_bounds = node.get("absoluteBoundingBox") or {}
    parent_bounds = parent.get("absoluteBoundingBox") or {}
    node_width = float(node_bounds.get("width", 0))
    node_height = float(node_bounds.get("height", 0))
    parent_width = float(parent_bounds.get("width", 0))
    parent_height = float(parent_bounds.get("height", 0))
    left = float(node_bounds.get("x", 0)) - float(parent_bounds.get("x", 0))
    top = float(node_bounds.get("y", 0)) - float(parent_bounds.get("y", 0))
    right = parent_width - left - node_width
    bottom = parent_height - top - node_height

    constraints = node.get("constraints") or {}
    horizontal = _constraint_axis(
        constraints.get("horizontal"),
        allowed={"LEFT", "RIGHT", "CENTER", "LEFT_RIGHT", "SCALE"},
        default="LEFT",
    )
    vertical = _constraint_axis(
        constraints.get("vertical"),
        allowed={"TOP", "BOTTOM", "CENTER", "TOP_BOTTOM", "SCALE"},
        default="TOP",
    )
    if horizontal == "CENTER" and parent_width > 0:
        left = (parent_width - node_width) / 2
    if vertical == "CENTER" and parent_height > 0:
        top = (parent_height - node_height) / 2

    return round_stack_placement(
        StackPlacement(
            horizontal=cast(HorizontalConstraint, horizontal),
            vertical=cast(VerticalConstraint, vertical),
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            width=node_width if node_width > 0 else None,
            height=node_height if node_height > 0 else None,
        )
    )


def reconcile_stack_placement_top_from_edges(
    placement: StackPlacement,
    *,
    parent_height: float | None,
) -> StackPlacement:
    """Reconcile TOP-pinned ``top`` when Figma edges imply a different value."""
    if parent_height is None or parent_height <= 0:
        return placement
    bottom = placement.bottom
    height = placement.height
    if bottom is None or bottom <= 0 or height is None or height <= 0:
        return placement
    if placement.top is None and bottom is not None and bottom > 0:
        inferred_only_top = parent_height - bottom - height
        rounded = round_geometry(inferred_only_top)
        return placement.model_copy(
            update={"top": rounded if rounded is not None else inferred_only_top},
        )
    top = placement.top if placement.top is not None else 0.0
    inferred_top = parent_height - bottom - height
    if abs(inferred_top - top) <= 1.0:
        return placement
    if placement.vertical == "BOTTOM":
        rounded = round_geometry(inferred_top)
        return placement.model_copy(
            update={"top": rounded if rounded is not None else inferred_top}
        )
    if (
        bottom <= _BOTTOM_ANCHORED_MAX_MARGIN_PX
        and abs(inferred_top - top) >= _BOTTOM_ANCHORED_MIN_TOP_DELTA_PX
    ):
        rounded = round_geometry(inferred_top)
        return placement.model_copy(
            update={"top": rounded if rounded is not None else inferred_top}
        )
    if top <= 1.0:
        rounded = round_geometry(inferred_top)
        return placement.model_copy(
            update={"top": rounded if rounded is not None else inferred_top}
        )
    return placement


def clamp_stack_child_placement_to_parent(
    placement: StackPlacement,
    parent_width: float,
) -> StackPlacement:
    """Clamp edge-anchored bars that bleed past the parent artboard (FID-19).

    Args:
        placement: Child ``stackPlacement`` inside a bounded ``STACK``.
        parent_width: Parent stack width in logical pixels.

    Returns:
        Placement constrained to ``[0, parent_width]`` when overflow is detected.
    """
    _OVERFLOW_EPSILON = 0.5
    if parent_width <= 0:
        return placement
    width = placement.width
    if width is None or width <= 0:
        return placement
    left = float(placement.left)
    right_edge = left + width
    if left >= -_OVERFLOW_EPSILON and right_edge <= parent_width + _OVERFLOW_EPSILON:
        return placement
    if (
        left >= -_OVERFLOW_EPSILON
        and left < parent_width - _OVERFLOW_EPSILON
        and right_edge > parent_width + _OVERFLOW_EPSILON
    ):
        return placement
    new_left = max(0.0, left)
    new_width = min(width, parent_width - new_left)
    if new_width <= _OVERFLOW_EPSILON:
        return placement
    return placement.model_copy(
        update={
            "horizontal": "LEFT",
            "left": round_geometry(new_left),
            "right": 0.0,
            "width": round_geometry(new_width),
        }
    )


_PLACEMENT_OVERFLOW_EPSILON_PX = 0.5


def _sync_sizing_width_to_placement(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> CleanDesignTreeNode:
    """Keep ``sizing.width`` aligned with a clamped stack placement width."""
    width = placement.width
    if width is None or width <= 0:
        return node
    current = node.sizing.width
    if current is not None and abs(float(current) - float(width)) <= _PLACEMENT_OVERFLOW_EPSILON_PX:
        return node
    return node.model_copy(
        update={
            "sizing": node.sizing.model_copy(
                update={"width": round_geometry(width), "width_mode": SizingMode.FIXED}
            )
        }
    )


def reconcile_stack_placements_in_tree(
    root: CleanDesignTreeNode,
    *,
    allow_clamp: bool = True,
) -> CleanDesignTreeNode:
    """Apply edge-based top reconciliation for STACK children across the tree."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        parent_height = node.sizing.height
        if parent_height is None and node.stack_placement is not None:
            parent_height = node.stack_placement.height
        parent_width = node.sizing.width
        if parent_width is None and node.stack_placement is not None:
            parent_width = node.stack_placement.width
        children: list[CleanDesignTreeNode] = []
        for child in node.children:
            updated = child
            if (
                node.type == NodeType.STACK
                and child.stack_placement is not None
                and not child.render_boundary
            ):
                placement = child.stack_placement
                if parent_height is not None:
                    placement = reconcile_stack_placement_top_from_edges(
                        placement,
                        parent_height=parent_height,
                    )
                if parent_width is not None and parent_width > 0 and allow_clamp:
                    placement = clamp_stack_child_placement_to_parent(
                        placement,
                        float(parent_width),
                    )
                updated = child.model_copy(update={"stack_placement": placement})
                updated = _sync_sizing_width_to_placement(updated, placement)
            children.append(walk(updated))
        return node.model_copy(update={"children": children})

    return walk(root)


def extract_layout_position(
    node: dict[str, Any],
    parent: dict[str, Any] | None,
) -> tuple[Literal["AUTO", "ABSOLUTE"], float, float]:
    """Extract absolute positioning metadata relative to the parent bounds."""
    from figma_flutter_agent.parser.numeric_rounding import round_geometry

    if parent is not None:
        placement = extract_stack_placement(node, parent)
        if placement is not None:
            return "ABSOLUTE", placement.left, placement.top
    if node.get("layoutPositioning") != "ABSOLUTE":
        return "AUTO", 0.0, 0.0
    node_bounds = node.get("absoluteBoundingBox") or {}
    if parent is None:
        x = round_geometry(float(node_bounds.get("x", 0))) or 0.0
        y = round_geometry(float(node_bounds.get("y", 0))) or 0.0
        return "ABSOLUTE", x, y
    parent_bounds = parent.get("absoluteBoundingBox") or {}
    offset_x = (
        round_geometry(float(node_bounds.get("x", 0)) - float(parent_bounds.get("x", 0))) or 0.0
    )
    offset_y = (
        round_geometry(float(node_bounds.get("y", 0)) - float(parent_bounds.get("y", 0))) or 0.0
    )
    return "ABSOLUTE", offset_x, offset_y


def refine_text_stack_placement(
    node_type: NodeType,
    style: NodeStyle,
    parent_type: NodeType | None,
    placement: StackPlacement | None,
) -> StackPlacement | None:
    """Stretch centered text across parent Stack bounds so ``textAlign`` works."""
    if placement is None or node_type != NodeType.TEXT or parent_type != NodeType.STACK:
        return placement
    if style.text_align not in {"CENTER", "RIGHT"}:
        return placement
    if placement.left is not None and float(placement.left) > 1.5:
        return placement
    if (
        placement.right is not None
        and float(placement.right) > 1.5
        and (placement.left is None or float(placement.left) <= 1.5)
    ):
        return placement
    return placement.model_copy(
        update={
            "horizontal": "LEFT_RIGHT",
            "left": 0.0,
            "right": 0.0,
        }
    )


def _infer_stack_child_top(
    placement: StackPlacement,
    *,
    parent_height: float,
) -> float | None:
    """Resolve a child's top offset inside an absolute stack from edges or explicit top."""
    if placement.top is not None:
        return float(placement.top)
    bottom = placement.bottom
    height = placement.height
    if bottom is not None and height is not None and parent_height > 0:
        return parent_height - float(bottom) - float(height)
    return None
