"""Regression tests for reminders / day-picker screens."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from figma_flutter_agent.generator.background import collect_ambient_background_children
from figma_flutter_agent.generator.dart.llm_codegen import expand_text_positioned_widths_from_tree
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DUMP_CANDIDATES = (
    _REPO_ROOT.parent
    / "flutter-demo-project"
    / "demo_app"
    / ".debug"
    / "processed"
    / "reminders_layout.json",
    _REPO_ROOT.parent / "demo_app" / ".debug" / "processed" / "reminders_layout.json",
)


def _load_tree() -> CleanDesignTreeNode | None:
    for path in _DUMP_CANDIDATES:
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return CleanDesignTreeNode.model_validate(payload["cleanTree"])
    return None


def _load_fresh_tree() -> CleanDesignTreeNode | None:
    from figma_flutter_agent.parser.tree import build_clean_tree

    raw_path = _DUMP_CANDIDATES[0].parent.parent / "raw" / "reminders_layout.json"
    if not raw_path.is_file():
        return None
    root = json.loads(raw_path.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)
    return tree


def test_multiline_subtitle_width_not_expanded_to_single_line() -> None:
    subtitle = CleanDesignTreeNode(
        id="1:3429",
        name="hint",
        type=NodeType.TEXT,
        text="Any time you can choose but We recommend first thing in th morning.",
        style=NodeStyle(font_size=16.0, font_weight="w300", line_height=1.65),
        stack_placement=StackPlacement(left=20.0, top=113.2, width=317.0, height=48.0),
    )
    tree = CleanDesignTreeNode(
        id="1:3427",
        name="Reminders",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[subtitle],
    )
    screen = """
    Positioned(
      left: 20.0,
      top: 113.2,
      width: 317.0,
      child: Text('Any time you can choose but We recommend first thing in th morning.'),
    ),
    """
    updated = expand_text_positioned_widths_from_tree(screen, tree)
    assert "width: 612" not in updated
    assert "width: 317.0" in updated


def test_day_picker_stacks_are_not_ambient_background() -> None:
    tree = _load_tree()
    if tree is None:
        pytest.skip("reminders processed dump not available")
    ambient = collect_ambient_background_children(tree)
    ambient_ids = {node.id for node in ambient}
    assert "1:3454" not in ambient_ids


def test_rendered_reminders_layout_has_wrapped_subtitle_day_labels_and_home_bar() -> None:
    tree = _load_fresh_tree()
    if tree is None:
        pytest.skip("reminders raw dump not available")
    layout = render_layout_file(tree, feature_name="reminders", uses_svg=True)[
        "lib/generated/reminders_layout.dart"
    ]
    assert re.search(r"figma-1_3429.*?width:\s*317", layout, re.DOTALL)
    assert "_GeneratedWeekdayChipRow" in layout
    assert "label: 'SU'" in layout
    assert "line_2_1_3479" in layout or "figma-1_3479" in layout
    assert layout.count("BoxFit.cover") == 0
