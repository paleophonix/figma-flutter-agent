"""Legacy name-hint parse traps: laundered types must not classify (E2.5-G)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.generator.geometry.invariants.type_truth import (
    is_legacy_semantic_type_node,
)
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import WidgetIrKind


def _figma_leaf_frame(*, layer_name: str, node_id: str = "leaf-1") -> dict[str, object]:
    """Minimal Figma frame with one rectangle leaf named via legacy name-hint policy."""
    return {
        "id": "screen-1",
        "name": "Screen",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "itemSpacing": 0,
        "absoluteBoundingBox": {"x": 0, "y": 0, "width": 360, "height": 640},
        "children": [
            {
                "id": node_id,
                "name": layer_name,
                "type": "RECTANGLE",
                "absoluteBoundingBox": {"x": 16, "y": 24, "width": 280, "height": 48},
                "fills": [{"type": "SOLID", "color": {"r": 0.9, "g": 0.9, "b": 0.9, "a": 1.0}}],
                "strokes": [],
            },
        ],
    }


def _accepted_semantic_kinds(report) -> list[str]:
    assert report.semantic is not None
    return [node.kind for node in report.semantic.accepted]


def _kind_on_node(screen_ir, figma_id: str) -> str:
    def walk(node) -> str | None:
        if node.figma_id == figma_id:
            return node.kind.value
        for child in node.children:
            found = walk(child)
            if found is not None:
                return found
        return None

    found = walk(screen_ir.root)
    assert found is not None
    return found


@pytest.mark.parametrize("layer_name", ["input", "button", "card"])
def test_legacy_name_hint_leaf_has_zero_semantic_classifications(layer_name: str) -> None:
    """Rectangle named input/button/card via parser must not accept any semantic kind."""
    node_id = f"legacy-{layer_name}"
    tree, _, _, _ = build_clean_tree(_figma_leaf_frame(layer_name=layer_name, node_id=node_id))

    assert is_legacy_semantic_type_node(node_id), "parser must mark legacy name-hint type"

    screen_ir = default_screen_ir(tree)
    updated_ir, report = classify_screen_ir(screen_ir, tree)

    assert _accepted_semantic_kinds(report) == []
    kind = _kind_on_node(updated_ir, node_id)
    assert WidgetIrKind(kind) not in SEMANTIC_IR_KINDS
    assert report.semantic is not None
    assert node_id in report.semantic.legacy_semantic_type_detected
