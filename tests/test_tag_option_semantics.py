"""Semantics classification for Figma Tag option chip groups."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.parser.semantics.signals.chip_anatomy import (
    is_tag_option_chip_group,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    WidgetIrKind,
)
from tests.test_cluster_chip_labels import _tag_chip


def _tag_option_chip_group(node_id: str = "chips-group") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Chips",
        type=NodeType.STACK,
        sizing=Sizing(width=294.0, height=56.0),
        children=[
            _tag_chip("chip-1", label="could have more components"),
            _tag_chip("chip-2", label="complex"),
            _tag_chip("chip-3", label="only english", selected=True),
        ],
    )


def test_tag_option_group_detected_as_chip_choice() -> None:
    group = _tag_option_chip_group()
    assert is_tag_option_chip_group(group)

    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[group],
    )
    updated, report = classify_screen_ir(default_screen_ir(screen), screen)
    assert report.semantic is not None
    accepted = {node.figma_id: node.kind for node in report.semantic.accepted}
    assert accepted.get("chips-group") == WidgetIrKind.CHIP_CHOICE.value
    assert _find_kind(updated.root, "chips-group") == WidgetIrKind.CHIP_CHOICE.value


def _find_kind(node, figma_id: str) -> str | None:
    if node.figma_id == figma_id:
        return node.kind.value
    for child in node.children:
        found = _find_kind(child, figma_id)
        if found is not None:
            return found
    return None
