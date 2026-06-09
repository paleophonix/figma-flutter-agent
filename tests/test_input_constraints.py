"""INPUT min/max BoxConstraints normalization (ROB-01)."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.geometry.invariants.validate import validate_geometry_invariants
from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    HeightFit,
    NodeType,
    Sizing,
    WrapKind,
)


def _column(*children: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="col",
        name="Column",
        type=NodeType.COLUMN,
        sizing=Sizing(width=300.0, height=400.0),
        children=list(children),
    )


def _input(height: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=f"input-{int(height)}",
        name="Email",
        type=NodeType.INPUT,
        sizing=Sizing(width=280.0, height=height),
    )


_INVERTED_MAX_MIN = re.compile(
    r"maxHeight:\s*([\d.]+).*minHeight:\s*([\d.]+)",
    re.DOTALL,
)


def _assert_no_inverted_height_constraints(dart: str) -> None:
    for match in _INVERTED_MAX_MIN.finditer(dart):
        max_height = float(match.group(1))
        min_height = float(match.group(2))
        assert max_height >= min_height


def test_input_constraints_below_touch_min_drop_max_height() -> None:
    for frame_h in (32.0, 40.0, 47.0):
        planned = plan_geometry_tree(_column(_input(frame_h)))
        slot = planned.children[0].layout_slot
        assert slot is not None
        assert slot.height_fit == HeightFit.MIN
        assert slot.min_height is not None and slot.min_height >= 48.0
        assert slot.max_height is None
        assert not validate_geometry_invariants(planned, require_layout_slots=True)


def test_input_emit_never_inverts_box_constraints() -> None:
    for frame_h in (32.0, 40.0, 47.0):
        planned = plan_geometry_tree(_column(_input(frame_h)))
        input_node = planned.children[0]
        slot = input_node.layout_slot
        assert slot is not None
        slot = slot.model_copy(
            update={
                "wraps": (*slot.wraps, WrapKind.CONSTRAINED_BOX),
                "min_height": 48.0,
                "max_height": frame_h,
            }
        )
        forced = input_node.model_copy(update={"layout_slot": slot})
        body = render_node_body(forced, uses_svg=False, parent_type=NodeType.COLUMN)
        _assert_no_inverted_height_constraints(body)
