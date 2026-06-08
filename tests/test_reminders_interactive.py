"""Interactive control detection and codegen for reminders-style screens."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.parser.interaction import (
    WEEKDAY_CHIP_ROW_NAME,
    looks_like_weekday_chip_stack,
    looks_like_wheel_time_picker_stack,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.layout import reconcile_weekday_chip_row_in_tree
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROCESSED_DUMP = (
    _REPO_ROOT.parent
    / "flutter-demo-project"
    / "demo_app"
    / ".figma_debug"
    / "processed"
    / "reminders_layout.json"
)
_RAW_DUMP = (
    _REPO_ROOT.parent
    / "flutter-demo-project"
    / "demo_app"
    / ".figma_debug"
    / "raw"
    / "reminders_layout.json"
)


def _load_processed_tree() -> CleanDesignTreeNode | None:
    if not _PROCESSED_DUMP.is_file():
        return None
    payload = json.loads(_PROCESSED_DUMP.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload["cleanTree"])


def _load_fresh_tree() -> CleanDesignTreeNode | None:
    if not _RAW_DUMP.is_file():
        return None
    root = json.loads(_RAW_DUMP.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)
    return tree


def _save_button_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:3466",
        name="Group 6799",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(left=20.0, top=694.0, width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="1:3467",
                name="Rectangle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=374.0, height=63.0),
                style=NodeStyle(background_color="0xFF8E97FD", border_radius=38.0),
            ),
            CleanDesignTreeNode(
                id="1:3468",
                name="SAVE",
                type=NodeType.TEXT,
                text="SAVE",
                stack_placement=StackPlacement(
                    horizontal="LEFT_RIGHT",
                    bottom=24.5,
                    width=374.0,
                    height=17.1,
                ),
            ),
        ],
    )


def test_save_stack_classified_as_button() -> None:
    assert stack_interaction_kind(_save_button_stack()) == "button"


def test_weekday_chip_row_reconcile_merges_chips() -> None:
    tree = _load_processed_tree()
    if tree is None:
        pytest.skip("reminders processed dump not available")
    updated = reconcile_weekday_chip_row_in_tree(tree)
    row_nodes = [
        node
        for node in updated.children
        if node.name == WEEKDAY_CHIP_ROW_NAME
    ]
    assert len(row_nodes) == 1
    assert len(row_nodes[0].children) >= 5
    assert all(looks_like_weekday_chip_stack(chip) for chip in row_nodes[0].children)


def test_rendered_reminders_layout_emits_interactive_controls() -> None:
    tree = _load_fresh_tree()
    if tree is None:
        pytest.skip("reminders raw dump not available")
    reconciled = reconcile_weekday_chip_row_in_tree(tree)
    picker = next(
        (child for child in reconciled.children if looks_like_wheel_time_picker_stack(child)),
        None,
    )
    assert picker is not None, "time wheel picker stack should remain in clean tree"
    layout = render_layout_file(reconciled, feature_name="reminders", uses_svg=True)[
        "lib/generated/reminders_layout.dart"
    ]
    assert "_GeneratedWeekdayChipRow" in layout
    assert "_GeneratedTimeWheelPicker" in layout
    assert "CupertinoPicker" in layout
    assert "InkWell(" in layout
    assert "onTap:" in layout
    assert "Alignment.center" in layout
    assert "Text('SAVE'" in layout
    assert "MouseRegion(" in layout or "GestureDetector(" in layout
