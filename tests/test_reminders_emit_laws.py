"""Regression tests for reminders-class interactive emit laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.extracted import emit_extracted_widget_code_from_ir
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.passes.policy import resolve_layout_pass_policy
from figma_flutter_agent.generator.ir.validate.graph import sync_screen_ir_graph_to_clean_tree
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
from figma_flutter_agent.generator.layout.interactive_time import extract_wheel_picker_columns
from figma_flutter_agent.generator.layout.widget_roots import (
    strip_stack_parent_data_wrappers,
    validate_widget_build_has_no_parent_data_root,
)
from figma_flutter_agent.generator.normalize import normalize_clean_tree, reconcile_layout_tree
from figma_flutter_agent.parser.interaction import layout_fact_wheel_time_picker_stack
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    ScreenIr,
    Sizing,
    SizingMode,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)
from figma_flutter_agent.config import load_settings

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LIMBO_PROCESSED = _REPO_ROOT / ".debug" / "screen" / "limbo" / "reminders" / "processed.json"
_LIMBO_PRE_EMIT = _REPO_ROOT / ".debug" / "screen" / "limbo" / "reminders" / "pre_emit.json"


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


def test_strip_stack_parent_data_wrappers_removes_positioned_root() -> None:
    """Law: extracted_widget_root_must_not_emit_parent_data_widgets."""
    wrapped = (
        "Positioned(left: 20.0, top: 10.0, width: 100.0, height: 80.0, "
        "child: _GeneratedTimeWheelPicker(columns: const [], height: 80.0))"
    )
    stripped = strip_stack_parent_data_wrappers(wrapped)
    assert stripped.startswith("_GeneratedTimeWheelPicker(")
    assert not stripped.startswith("Positioned(")


def test_extracted_widget_materialization_strips_positioned_root() -> None:
    """Law: extracted_widget_root_must_not_emit_parent_data_widgets."""
    picker = CleanDesignTreeNode(
        id="1:wheel",
        name="wheel",
        type=NodeType.STACK,
        sizing=Sizing(width=300.0, height=192.0),
        stack_placement=StackPlacement(left=20.0, top=40.0, width=300.0, height=192.0),
        children=[
            CleanDesignTreeNode(
                id="1:h1",
                name="10",
                type=NodeType.TEXT,
                text="10",
                stack_placement=StackPlacement(left=20.0, top=10.0, width=20.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:h2",
                name="11",
                type=NodeType.TEXT,
                text="11",
                stack_placement=StackPlacement(left=24.0, top=70.0, width=20.0, height=24.0),
                style=NodeStyle(font_weight="700"),
            ),
            CleanDesignTreeNode(
                id="1:h3",
                name="12",
                type=NodeType.TEXT,
                text="12",
                stack_placement=StackPlacement(left=20.0, top=130.0, width=20.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:m1",
                name="29",
                type=NodeType.TEXT,
                text="29",
                stack_placement=StackPlacement(left=120.0, top=10.0, width=20.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:m2",
                name="30",
                type=NodeType.TEXT,
                text="30",
                stack_placement=StackPlacement(left=120.0, top=70.0, width=20.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:m3",
                name="31",
                type=NodeType.TEXT,
                text="31",
                stack_placement=StackPlacement(left=120.0, top=130.0, width=20.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:am",
                name="AM",
                type=NodeType.TEXT,
                text="AM",
                stack_placement=StackPlacement(left=220.0, top=70.0, width=20.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:pm",
                name="PM",
                type=NodeType.TEXT,
                text="PM",
                stack_placement=StackPlacement(left=220.0, top=130.0, width=20.0, height=24.0),
            ),
        ],
    )
    widget_ir = WidgetIrNode(figma_id="1:wheel", kind=WidgetIrKind.STACK)
    code = emit_extracted_widget_code_from_ir(
        widget_ir,
        clean_tree=picker,
        widget_name="Group6804Widget",
        ctx=IrEmitContext(uses_svg=False, responsive_enabled=False),
    )
    assert validate_widget_build_has_no_parent_data_root(code) == []
    assert "return Positioned(" not in code


def test_wheel_column_groups_merge_selected_hour_lane() -> None:
    """Law: wheel_column_groups_same_axis_numbers_incl_selected."""
    picker = CleanDesignTreeNode(
        id="1:wheel",
        name="wheel",
        type=NodeType.STACK,
        sizing=Sizing(width=300.0, height=192.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=300.0, height=192.0),
        children=[
            CleanDesignTreeNode(
                id="1:10",
                name="10",
                type=NodeType.TEXT,
                text="10",
                stack_placement=StackPlacement(left=20.0, top=10.0, width=20.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:12",
                name="12",
                type=NodeType.TEXT,
                text="12",
                stack_placement=StackPlacement(left=20.0, top=130.0, width=20.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:11",
                name="11",
                type=NodeType.TEXT,
                text="11",
                stack_placement=StackPlacement(left=28.0, top=70.0, width=20.0, height=24.0),
                style=NodeStyle(font_weight="700"),
            ),
            CleanDesignTreeNode(
                id="1:30",
                name="30",
                type=NodeType.TEXT,
                text="30",
                stack_placement=StackPlacement(left=120.0, top=70.0, width=20.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:am",
                name="AM",
                type=NodeType.TEXT,
                text="AM",
                stack_placement=StackPlacement(left=220.0, top=70.0, width=20.0, height=24.0),
            ),
        ],
    )
    columns = extract_wheel_picker_columns(picker)
    assert len(columns) == 3
    assert columns[0].labels == ("10", "11", "12")
    assert columns[0].selected_index == 1


def test_time_wheel_helpers_emit_selection_overlay_lines() -> None:
    """Law: wheel_selection_overlay_is_two_lines_not_box."""
    source = render_widget_file(
        class_name="Group6804Widget",
        body="_GeneratedTimeWheelPicker(columns: const [], height: 120.0)",
        uses_svg=False,
        source_file="lib/widgets/group6804_widget.dart",
    )
    fixed = ensure_interactive_layout_helpers(source)
    assert "useMagnifier: false" in fixed
    assert "IgnorePointer" in fixed
    assert "height: 1.0" in fixed


def _load_limbo_screen_ir() -> ScreenIr | None:
    if not _LIMBO_PRE_EMIT.is_file():
        return None
    payload = json.loads(_LIMBO_PRE_EMIT.read_text(encoding="utf-8"))
    return ScreenIr.model_validate(payload["screenIr"])


def test_layout_passes_keep_weekday_chip_row_emit() -> None:
    """Law: compact_chip_row_emit_must_win_over_chip_choice_ir_and_vector_boundary."""
    tree = _load_limbo_processed_tree()
    screen_ir = _load_limbo_screen_ir()
    if tree is None or screen_ir is None:
        pytest.skip("limbo reminders artifacts not available")
    normalized = normalize_clean_tree(
        tree,
        screen_ir=screen_ir,
        apply_render_safety=True,
        use_geometry_planner=True,
        archetype_reconcile=False,
    )
    settings = load_settings()
    threshold, inject_scroll, responsive_reflow, preserve_placement = resolve_layout_pass_policy(
        settings.agent
    )
    screen_ir, normalized = apply_ir_layout_passes(
        screen_ir,
        normalized,
        macro_height_threshold_px=threshold,
        inject_root_scroll_host=inject_scroll,
        responsive_reflow_enabled=responsive_reflow,
        preserve_placement=preserve_placement,
    )
    from figma_flutter_agent.generator.normalize import replan_geometry_after_layout_passes

    normalized = replan_geometry_after_layout_passes(normalized)
    layout = render_layout_file(
        normalized,
        feature_name="reminders",
        uses_svg=True,
        screen_ir=screen_ir,
        use_geometry_planner=True,
        skip_layout_reconcile=True,
    )["lib/generated/reminders_layout.dart"]
    build = layout.split("Widget build(BuildContext context)", 1)[1]
    assert "_GeneratedWeekdayChipRow(" in build
    assert "ellipse_31_1_3455" not in build


def test_sync_chip_choice_selected_from_clean_tree() -> None:
    """Law: chip_choice_selected_state_must_follow_semantic_verdict."""
    chip = CleanDesignTreeNode(
        id="1:3454",
        name="SU",
        type=NodeType.STACK,
        sizing=Sizing(width=40.0, height=40.0),
        style=NodeStyle(background_color="0xFF3F414E"),
        children=[
            CleanDesignTreeNode(
                id="1:3456",
                name="SU",
                type=NodeType.TEXT,
                text="SU",
            ),
        ],
    )
    root = CleanDesignTreeNode(
        id="1:root",
        name="root",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[chip],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="1:3454",
                    kind=WidgetIrKind.CHIP_CHOICE,
                    is_selected=False,
                )
            ],
        )
    )
    sync_screen_ir_graph_to_clean_tree(screen_ir, root)
    child = screen_ir.root.children[0]
    assert child.is_selected is True


def test_layout_skips_wheel_helpers_for_extracted_roots() -> None:
    """Law: generated_helpers_must_not_be_duplicated_across_extracted_widget_and_screen_layout."""
    tree = _load_limbo_processed_tree()
    screen_ir = _load_limbo_screen_ir()
    if tree is None or screen_ir is None:
        pytest.skip("limbo reminders artifacts not available")
    reconciled = reconcile_layout_tree(tree)
    wheel = next(
        child for child in reconciled.children if layout_fact_wheel_time_picker_stack(child)
    )
    wheel = wheel.model_copy(update={"extracted_widget_ref": "Group6804Widget"})
    patched = reconciled.model_copy(
        update={
            "children": [
                wheel if child.id == wheel.id else child for child in reconciled.children
            ]
        }
    )
    layout = render_layout_file(
        patched,
        feature_name="reminders",
        uses_svg=True,
        screen_ir=screen_ir,
    )["lib/generated/reminders_layout.dart"]
    assert layout.count("class _GeneratedTimeWheelPicker extends StatefulWidget") == 0
