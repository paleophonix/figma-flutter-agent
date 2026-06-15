"""Corpus gate: planner=on must produce zero HARD geometry violations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.errors import ParseError
from figma_flutter_agent.generator.geometry.affine import affine_det, transform_point
from figma_flutter_agent.generator.geometry.invariants.reporting import (
    partition_geometry_violations,
)
from figma_flutter_agent.generator.geometry.invariants.validate import (
    validate_geometry_invariants,
)
from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.geometry_frames import affine2_from_figma_node
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    HeightFit,
    NodeType,
    Sizing,
    StackPlacement,
)

_LAYOUT_FIXTURES = sorted((Path(__file__).resolve().parent / "fixtures" / "layouts").glob("*.json"))


def _is_raw_figma_fixture(payload: dict) -> bool:
    return "layoutMode" in payload or (
        isinstance(payload.get("absoluteBoundingBox"), dict) and "type" not in payload
    )


def _load_fixture_tree(path: Path) -> CleanDesignTreeNode:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if _is_raw_figma_fixture(payload):
        tree, _, _, _ = build_clean_tree(payload)
        return tree
    return CleanDesignTreeNode.model_validate(payload)


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


def _assert_zero_hard_after_plan(tree: CleanDesignTreeNode) -> None:
    planned = plan_geometry_tree(tree)
    violations = validate_geometry_invariants(planned, require_layout_slots=True)
    hard, _ = partition_geometry_violations(violations)
    assert not hard, "; ".join(f"{v.code}@{v.node_id}" for v in hard)


@pytest.mark.parametrize("fixture_path", _LAYOUT_FIXTURES, ids=lambda p: p.name)
def test_corpus_fixture_zero_hard_violations(fixture_path: Path) -> None:
    tree = _load_fixture_tree(fixture_path)
    normalized = normalize_clean_tree(
        tree,
        apply_render_safety=False,
        use_geometry_planner=True,
    )
    violations = validate_geometry_invariants(normalized, require_layout_slots=True)
    hard, _ = partition_geometry_violations(violations)
    assert not hard, "; ".join(f"{v.code}@{v.node_id}" for v in hard)


def test_corpus_short_input_sub48_no_hard_violations() -> None:
    for frame_h in (32.0, 40.0, 47.0):
        _assert_zero_hard_after_plan(_column(_input(frame_h)))
        planned = plan_geometry_tree(_column(_input(frame_h)))
        slot = planned.children[0].layout_slot
        assert slot is not None
        assert slot.height_fit == HeightFit.MIN
        assert slot.max_height is None


def test_corpus_malformed_transform_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="malformed relativeTransform at node node-42"):
        affine2_from_figma_node(
            {
                "id": "node-42",
                "relativeTransform": "not-a-matrix",
            }
        )


def test_corpus_mirror_det_negative_raster_tier() -> None:
    raw = {
        "relativeTransform": [
            [-1.0, 0.0, 10.0],
            [0.0, 1.0, 5.0],
        ],
    }
    affine = affine2_from_figma_node(raw)
    assert affine_det(affine) < 0
    corners = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
    mapped = [transform_point(affine, x, y) for x, y in corners]
    assert mapped[0][0] > mapped[1][0]


def test_corpus_mixed_stack_preserves_interactive_z() -> None:
    static_bg = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.CONTAINER,
        stack_placement=StackPlacement(left=0.0, top=0.0, width=300.0, height=600.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=20.0, top=500.0, width=260.0, height=48.0),
    )
    deco = CleanDesignTreeNode(
        id="deco",
        name="Deco",
        type=NodeType.CONTAINER,
        stack_placement=StackPlacement(left=0.0, top=0.0, width=300.0, height=100.0),
    )
    stack = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=300.0, height=600.0),
        children=[static_bg, button, deco],
    )
    _assert_zero_hard_after_plan(stack)


def test_corpus_a11y_long_text_emit_no_hard() -> None:
    label = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        sizing=Sizing(width=280.0, height=120.0),
        text="A" * 200,
    )
    planned = plan_geometry_tree(_column(label))
    body = render_node_body(
        planned.children[0],
        uses_svg=False,
        parent_type=NodeType.COLUMN,
    )
    assert "Text(" in body
    violations = validate_geometry_invariants(planned, require_layout_slots=True)
    hard, _ = partition_geometry_violations(violations)
    assert not hard
