"""Render-safety validation for screen IR."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir_tree import default_screen_ir
from figma_flutter_agent.generator.ir_validate import (
    validate_extracted_widget_ir,
    validate_screen_ir,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    FlexWrapIr,
    NodeType,
    NodeStyle,
    ScreenIr,
    Sizing,
    SizingMode,
    StackPlacement,
    TypographyStyle,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrOverrides,
)


def _screen_root() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[],
    )


def test_validate_accepts_sign_up_fixture_layout() -> None:
    from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
    from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
    from figma_flutter_agent.generator.ir_tree import default_screen_ir

    tree = load_layout_tree("sign_up_and_sign_in")
    planned = build_fixture_planned_files("sign_up_and_sign_in")
    layout_key = "lib/generated/sign_up_and_sign_in_layout.dart"
    assert layout_key in planned
    validate_screen_ir(default_screen_ir(tree), tree)


def test_validate_accepts_horizontal_stroke_line_without_placement_height() -> None:
    root = _screen_root()
    divider = CleanDesignTreeNode(
        id="line",
        name="Line",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.HUG, height_mode=SizingMode.HUG, width=143.0, height=0.0),
        style=NodeStyle(border_width=5.0, border_color="0xFFE6E6E6", has_stroke=True),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=136.0,
            top=838.0,
            right=135.0,
            bottom=14.0,
            width=143.0,
        ),
    )
    root = root.model_copy(update={"children": [divider]})
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[WidgetIrNode(figma_id="line", kind=WidgetIrKind.AUTO, children=[])],
        ),
    )
    validate_screen_ir(screen_ir, root)


def test_validate_rejects_unbounded_stack_width() -> None:
    root = _screen_root()
    child = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=40.0, top=100.0, horizontal="LEFT"),
        sizing=Sizing(width_mode=SizingMode.HUG),
    )
    root = root.model_copy(update={"children": [child]})
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.STACK,
            children=[WidgetIrNode(figmaId="btn", kind=WidgetIrKind.BUTTON)],
        ),
    )
    with pytest.raises(GenerationError, match="bounded width"):
        validate_screen_ir(screen_ir, root)


def test_validate_rejects_scroll_in_column_without_expanded() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="list",
                name="List",
                type=NodeType.COLUMN,
                scroll_axis="vertical",
                sizing=Sizing(height_mode=SizingMode.FILL, height=800.0),
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.COLUMN,
            children=[
                WidgetIrNode(figmaId="list", kind=WidgetIrKind.COLUMN, wrap=FlexWrapIr.NONE),
            ],
        ),
    )
    with pytest.raises(GenerationError, match="scroll/grid host"):
        validate_screen_ir(screen_ir, root)


def test_validate_accepts_scroll_in_column_with_expanded_wrap() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="list",
                name="List",
                type=NodeType.COLUMN,
                scroll_axis="vertical",
                sizing=Sizing(height_mode=SizingMode.FILL, height=800.0),
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.COLUMN,
            children=[
                WidgetIrNode(
                    figmaId="list",
                    kind=WidgetIrKind.COLUMN,
                    wrap=FlexWrapIr.EXPANDED,
                ),
            ],
        ),
    )
    validate_screen_ir(screen_ir, root)


def test_validate_rejects_low_contrast_button_label() -> None:
    root = _screen_root()
    button = CleanDesignTreeNode(
        id="cta",
        name="CTA",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(
            left=40.0,
            top=600.0,
            width=334.0,
            height=56.0,
        ),
        style=NodeStyle(background_color="0xFF664FA3"),
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Label",
                type=NodeType.TEXT,
                text="LOG IN",
                style=NodeStyle(text_color="0xFF000000"),
            ),
        ],
    )
    root = root.model_copy(update={"children": [button]})
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figmaId="cta",
                    kind=WidgetIrKind.BUTTON,
                    children=[WidgetIrNode(figmaId="label", kind=WidgetIrKind.TEXT)],
                ),
            ],
        ),
    )
    with pytest.raises(GenerationError, match="contrast"):
        validate_screen_ir(screen_ir, root)


def test_apply_guards_clamps_mild_viewport_overflow() -> None:
    root = _screen_root()
    child = CleanDesignTreeNode(
        id="3:627",
        name="Offscreen chip",
        type=NodeType.TEXT,
        text="X",
        stack_placement=StackPlacement(left=418.0, top=39.3, width=80.0, height=24.0),
    )
    root = root.model_copy(update={"children": [child]})
    screen_ir = default_screen_ir(root)
    validate_screen_ir(screen_ir, root)
    assert child.stack_placement is not None
    assert child.stack_placement.left is not None
    assert child.stack_placement.left < 418.0


def test_validate_rejects_viewport_hallucination() -> None:
    root = _screen_root()
    child = CleanDesignTreeNode(
        id="ghost",
        name="Ghost",
        type=NodeType.TEXT,
        text="Nope",
        stack_placement=StackPlacement(left=20.0, top=2500.0, width=100.0, height=24.0),
    )
    root = root.model_copy(update={"children": [child]})
    screen_ir = default_screen_ir(root)
    validate_screen_ir(screen_ir, root)


def test_validate_sets_nested_scroll_constraints_for_root_stack_child() -> None:
    root = _screen_root()
    inner = CleanDesignTreeNode(
        id="list",
        name="List",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        sizing=Sizing(width=300.0, height=400.0),
    )
    root = root.model_copy(update={"children": [inner]})
    screen_ir = default_screen_ir(root)
    validate_screen_ir(screen_ir, root)
    assert inner.nested_scroll_constraints is True


def test_validate_auto_wraps_row_text_in_flexible() -> None:
    label = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        text="Long copy",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=200.0),
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width=300.0),
        children=[label],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=414.0, height=896.0),
        children=[row],
    )
    ir_label = WidgetIrNode(figmaId="label", kind=WidgetIrKind.TEXT)
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.COLUMN,
            children=[
                WidgetIrNode(
                    figmaId="row",
                    kind=WidgetIrKind.ROW,
                    children=[ir_label],
                ),
            ],
        ),
    )
    validate_screen_ir(screen_ir, root)
    assert ir_label.wrap == FlexWrapIr.FLEXIBLE_LOOSE


def test_validate_rejects_missing_asset_on_disk(tmp_path: Path) -> None:
    root = _screen_root()
    icon = CleanDesignTreeNode(
        id="icon",
        name="Icon",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/missing.svg",
        stack_placement=StackPlacement(left=0.0, top=0.0, width=24.0, height=24.0),
    )
    root = root.model_copy(update={"children": [icon]})
    screen_ir = default_screen_ir(root)
    with pytest.raises(GenerationError, match="missing asset"):
        validate_screen_ir(screen_ir, root, project_dir=tmp_path)


def test_validate_sets_min_touch_target_for_small_button() -> None:
    root = _screen_root()
    tiny = CleanDesignTreeNode(
        id="close",
        name="Close",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=10.0, top=10.0, width=16.0, height=16.0),
    )
    root = root.model_copy(update={"children": [tiny]})
    screen_ir = default_screen_ir(root)
    validate_screen_ir(screen_ir, root)
    assert tiny.min_touch_target == 44.0


def test_validate_rejects_duplicate_figma_ids() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(id="dup", name="A", type=NodeType.TEXT, text="a"),
        ],
    )
    dup = WidgetIrNode(figmaId="dup", kind=WidgetIrKind.TEXT)
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.COLUMN,
            children=[dup, dup],
        ),
    )
    with pytest.raises(GenerationError, match="more than once"):
        validate_screen_ir(screen_ir, root)


def test_validate_without_guards_skips_min_touch_auto_fix() -> None:
    root = _screen_root()
    tiny = CleanDesignTreeNode(
        id="close",
        name="Close",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=10.0, top=10.0, width=16.0, height=16.0),
    )
    root = root.model_copy(update={"children": [tiny]})
    screen_ir = default_screen_ir(root)
    validate_screen_ir(screen_ir, root, apply_guards=False)
    assert tiny.min_touch_target is None


def test_validate_rejects_stack_ghost_occlusion() -> None:
    root = _screen_root()
    button = CleanDesignTreeNode(
        id="cta",
        name="CTA",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=40.0, top=400.0, width=120.0, height=48.0),
    )
    veil = CleanDesignTreeNode(
        id="veil",
        name="Veil",
        type=NodeType.VECTOR,
        stack_placement=StackPlacement(left=30.0, top=390.0, width=140.0, height=70.0),
    )
    root = root.model_copy(update={"children": [button, veil]})
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(figmaId="cta", kind=WidgetIrKind.BUTTON),
                WidgetIrNode(figmaId="veil", kind=WidgetIrKind.AUTO),
            ],
        ),
    )
    with pytest.raises(GenerationError, match="above interactive"):
        validate_screen_ir(screen_ir, root)


def test_validate_applies_keyboard_scroll_on_nearest_column() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="password",
                name="Password",
                type=NodeType.INPUT,
                sizing=Sizing(width=334.0, height=48.0),
                offset_y=700.0,
            ),
        ],
    )
    screen_ir = default_screen_ir(root)
    validate_screen_ir(screen_ir, root)
    assert root.scroll_axis == "vertical"


def test_validate_rejects_keyboard_trap_without_column_host() -> None:
    password = CleanDesignTreeNode(
        id="password",
        name="Password",
        type=NodeType.INPUT,
        sizing=Sizing(width=334.0, height=48.0),
        offset_y=700.0,
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.ROW,
        sizing=Sizing(width=414.0, height=896.0),
        children=[password],
    )
    screen_ir = default_screen_ir(root)
    with pytest.raises(GenerationError, match="keyboard"):
        validate_screen_ir(screen_ir, root)


def test_validate_resolves_token_name_in_color_overrides() -> None:
    tokens = DesignTokens(colors={"color6": "0xFF664FA3"})
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="1:3661",
                name="Chip",
                type=NodeType.CONTAINER,
            ),
        ],
    )
    chip_ir = WidgetIrNode(
        figmaId="1:3661",
        kind=WidgetIrKind.CONTAINER,
        overrides=WidgetIrOverrides(backgroundColor="color6"),
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.COLUMN,
            children=[chip_ir],
        ),
    )
    validate_screen_ir(screen_ir, root, tokens=tokens)
    assert chip_ir.overrides is not None
    assert chip_ir.overrides.background_color == "0xFF664FA3"


def test_validate_snaps_token_colors_in_overrides() -> None:
    tokens = DesignTokens(
        colors={"primary": "0xFF112233"},
        typography={"body": TypographyStyle(fontSize=16.0, fontWeight="w400")},
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Label",
                type=NodeType.TEXT,
                text="Hi",
            ),
        ],
    )
    label_ir = WidgetIrNode(
        figmaId="label",
        kind=WidgetIrKind.TEXT,
        overrides=WidgetIrOverrides(textColor="0xFF112244"),
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.COLUMN,
            children=[label_ir],
        ),
    )
    validate_screen_ir(screen_ir, root, tokens=tokens)
    assert label_ir.overrides is not None
    assert label_ir.overrides.text_color == "0xFF112233"


def test_validate_extracted_widget_ir_skips_pruned_subtree_root() -> None:
    """Subtree pruning removes node ids from clean tree; LLM widgetIr must not hard-fail."""
    root = _screen_root()
    widget = ExtractedWidget(
        widget_name="Group17Widget",
        code="class Group17Widget extends StatelessWidget { const Group17Widget({super.key}); @override Widget build(BuildContext c) => const SizedBox.shrink(); }",
        widget_ir=WidgetIrNode(figma_id="1:3665", kind=WidgetIrKind.STACK),
    )
    validate_extracted_widget_ir(widget, root)
