"""Regression tests for reminders-class interactive emit laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file, render_widget_file
from figma_flutter_agent.generator.layout.choice_chip_row import (
    layout_fact_circular_option_chip_row_host,
)
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    layout_fact_stack_circular_option_glyph_host,
)
from figma_flutter_agent.generator.layout.interactive_chrome import (
    ensure_interactive_layout_helpers,
)
from figma_flutter_agent.generator.normalize import reconcile_layout_tree
from figma_flutter_agent.parser.interaction import layout_fact_wheel_time_picker_stack
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LIMBO_PROCESSED = _REPO_ROOT / ".debug" / "screen" / "limbo" / "reminders" / "processed.json"


def _load_limbo_processed_tree() -> CleanDesignTreeNode | None:
    if not _LIMBO_PROCESSED.is_file():
        return None
    payload = json.loads(_LIMBO_PROCESSED.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload["cleanTree"])


def _circular_glyph_chip(node_id: str, label: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="chip",
        type=NodeType.STACK,
        sizing=Sizing(
            width=40.0,
            height=40.0,
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
        ),
        style=NodeStyle(background_color="0xFFE0E0E0"),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}-surface",
                name="surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=40.0, height=40.0),
                style=NodeStyle(background_color="0xFFCCCCCC", border_radius=20.0),
            ),
            CleanDesignTreeNode(
                id=f"{node_id}-label",
                name="label",
                type=NodeType.TEXT,
                text=label,
                stack_placement=StackPlacement(
                    horizontal="LEFT_RIGHT",
                    vertical="TOP_BOTTOM",
                    width=40.0,
                    height=20.0,
                ),
            ),
        ],
    )


def test_circular_option_chip_row_host_rejects_mixed_screen_root() -> None:
    """Law: screen_root_must_not_match_circular_option_chip_row_host."""
    tree = _load_limbo_processed_tree()
    if tree is None:
        pytest.skip("limbo reminders processed dump not available")
    assert layout_fact_circular_option_chip_row_host(tree) is False


def test_circular_option_chip_row_host_accepts_dedicated_row() -> None:
    row = CleanDesignTreeNode(
        id="size-row",
        name="Size row",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=48.0),
        children=[
            _circular_glyph_chip("chip-s", "S"),
            _circular_glyph_chip("chip-m", "M"),
            _circular_glyph_chip("chip-l", "L"),
        ],
    )
    assert all(layout_fact_stack_circular_option_glyph_host(child) for child in row.children)
    assert layout_fact_circular_option_chip_row_host(row) is True


def test_screen_root_emit_preserves_timer_weekday_row_and_save() -> None:
    """Law: compact_chip_band + primary CTA survive when root is not a chip-row host."""
    tree = _load_limbo_processed_tree()
    if tree is None:
        pytest.skip("limbo reminders processed dump not available")
    reconciled = reconcile_layout_tree(tree)
    picker = next(
        (child for child in reconciled.children if layout_fact_wheel_time_picker_stack(child)),
        None,
    )
    assert picker is not None
    layout = render_layout_file(reconciled, feature_name="reminders", uses_svg=True)[
        "lib/generated/reminders_layout.dart"
    ]
    assert "_GeneratedWeekdayChipRow" in layout
    assert "_GeneratedTimeWheelPicker" in layout
    assert "Text('SAVE'" in layout
    assert "_GeneratedCircularOptionChipRow" not in layout


def test_widget_file_includes_interactive_time_wheel_helpers() -> None:
    """Law: extracted_widget_files_must_bundle_interactive_helper_classes."""
    body = "_GeneratedTimeWheelPicker(columns: const [], height: 120.0)"
    source = render_widget_file(
        class_name="Group6804Widget",
        body=body,
        uses_svg=False,
        package_name="limbo",
        source_file="lib/widgets/group6804_widget.dart",
    )
    assert "class _GeneratedTimeWheelPicker extends StatefulWidget" in source
    assert "class _WheelPickerColumnSpec" in source
    assert "package:flutter/cupertino.dart" in source


def test_ensure_interactive_layout_helpers_repairs_llm_widget_file() -> None:
    broken = """import 'package:flutter/material.dart';

class Group6804Widget extends StatelessWidget {
  const Group6804Widget({super.key});

  @override
  Widget build(BuildContext context) {
    return _GeneratedTimeWheelPicker(columns: const [], height: 120.0);
  }
}
"""
    fixed = ensure_interactive_layout_helpers(broken)
    assert "class _GeneratedTimeWheelPicker extends StatefulWidget" in fixed
    assert "package:flutter/cupertino.dart" in fixed
