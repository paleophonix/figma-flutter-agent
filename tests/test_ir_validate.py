"""Render-safety validation for screen IR."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.ir.validate import (
    realign_screen_ir_children_to_clean_tree,
    validate_extracted_widget_ir,
    validate_screen_ir,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    FlexWrapIr,
    NodeStyle,
    NodeType,
    ScreenIr,
    Sizing,
    SizingMode,
    StackPlacement,
    TypographyStyle,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrOverrides,
    WidgetIrRef,
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
    from figma_flutter_agent.generator.ir.tree import default_screen_ir

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
        sizing=Sizing(
            width_mode=SizingMode.HUG, height_mode=SizingMode.HUG, width=143.0, height=0.0
        ),
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


def test_validate_accepts_grid_in_column_without_expanded_wrap() -> None:
    """GRID under COLUMN with non-FILL height uses shrinkWrap at emit time."""
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=800.0),
        children=[
            CleanDesignTreeNode(
                id="610:537",
                name="Container",
                type=NodeType.GRID,
                sizing=Sizing(width_mode=SizingMode.FILL, width=357.0, height=314.0),
                grid_column_count=2,
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.COLUMN,
            children=[WidgetIrNode(figmaId="610:537", kind=WidgetIrKind.AUTO)],
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
        validate_screen_ir(screen_ir, root, strict_contrast=True)


def test_validate_skips_low_contrast_when_gate_off() -> None:
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
    validate_screen_ir(screen_ir, root)


def test_validate_accepts_muted_text_on_white_pill_over_screen_fill() -> None:
    """Contrast uses the pill ROW fill, not a distant screen CONTAINER (chats chip)."""
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        style=NodeStyle(background_color="0xFFF6F6F2"),
        children=[
            CleanDesignTreeNode(
                id="pill",
                name="Background+Border",
                type=NodeType.ROW,
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_color="0xFFE4E4E7",
                    has_stroke=True,
                ),
                children=[
                    CleanDesignTreeNode(
                        id="label",
                        name="Closed",
                        type=NodeType.TEXT,
                        text="Closed",
                        style=NodeStyle(text_color="0xFF71717B", font_size=12.0),
                    ),
                ],
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figmaId="pill",
                    kind=WidgetIrKind.ROW,
                    children=[WidgetIrNode(figmaId="label", kind=WidgetIrKind.TEXT)],
                ),
            ],
        ),
    )
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
    normalized = validate_screen_ir(screen_ir, root)
    clamped = normalized.children[0]
    assert clamped.stack_placement is not None
    assert clamped.stack_placement.left is not None
    assert clamped.stack_placement.left < 418.0


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


def test_validate_accepts_nested_stack_overflow_placement() -> None:
    """Parent-relative stackPlacement must not be checked against the root viewport."""
    overflow_image = CleanDesignTreeNode(
        id="610:833",
        name="image 19",
        type=NodeType.IMAGE,
        sizing=Sizing(width=376.1, height=210.0),
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(
            horizontal="RIGHT",
            left=-262.3,
            top=-59.0,
            right=-17.8,
            bottom=-55.0,
            width=376.1,
            height=210.0,
        ),
    )
    host_stack = CleanDesignTreeNode(
        id="281:12273",
        name="thumbnail",
        type=NodeType.STACK,
        sizing=Sizing(width=96.0, height=96.0),
        children=[overflow_image],
    )
    root = CleanDesignTreeNode(
        id="281:12205",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=1697.0),
        children=[host_stack],
    )
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
    normalized = validate_screen_ir(screen_ir, root)
    assert normalized.children[0].nested_scroll_constraints is True


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
    normalized = validate_screen_ir(screen_ir, root)
    assert normalized.children[0].min_touch_target == 44.0


def test_validate_sanitizes_duplicate_figma_ids() -> None:
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
    validate_screen_ir(screen_ir, root, apply_guards=False)
    assert len(screen_ir.root.children) == 1


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
    normalized = validate_screen_ir(screen_ir, root)
    assert normalized.scroll_axis == "vertical"


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


def test_validate_drops_unregistered_token_overrides_in_guard_path() -> None:
    tokens = DesignTokens(colors={"primary": "0xFF112233"})
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
        figma_id="label",
        kind=WidgetIrKind.TEXT,
        overrides=WidgetIrOverrides(text_color="#FF00FF"),
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.COLUMN,
            children=[label_ir],
        ),
    )
    validate_screen_ir(screen_ir, root, tokens=tokens)
    assert label_ir.overrides is not None
    assert label_ir.overrides.text_color is None


def test_validate_accepts_clean_tree_colors_missing_from_flat_tokens() -> None:
    """Button label colors from Figma must not fail when absent from deduped token map."""
    tokens = DesignTokens(
        colors={"primary": "0xFF3F414E"},
        typography={"body": TypographyStyle(fontSize=14.0, fontWeight="w500")},
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="1:3620",
                name="GET STARTED",
                type=NodeType.TEXT,
                text="GET STARTED",
                style=NodeStyle(text_color="0xFF000000"),
            ),
        ],
    )
    label_ir = WidgetIrNode(
        figmaId="1:3620",
        kind=WidgetIrKind.TEXT,
        overrides=WidgetIrOverrides(textColor="0xFF000000"),
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
    assert label_ir.overrides.text_color == "0xFF000000"


def test_validate_accepts_clean_tree_font_sizes_missing_from_flat_tokens() -> None:
    """Chip label font sizes from Figma must not fail when absent from deduped typography."""
    tokens = DesignTokens(
        colors={"primary": "0xFF2E7D32"},
        typography={"body": TypographyStyle(fontSize=11.0, fontWeight="w600")},
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="281:12717",
                name="Основной",
                type=NodeType.TEXT,
                text="Основной",
                style=NodeStyle(text_color="0xFF2E7D32", font_size=12.0),
            ),
        ],
    )
    label_ir = WidgetIrNode(
        figmaId="281:12717",
        kind=WidgetIrKind.TEXT,
        overrides=WidgetIrOverrides(textColor="0xFF2E7D32", fontSize=12.0),
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
    assert label_ir.overrides.font_size == 12.0


def test_validate_extracted_widget_ir_skips_pruned_subtree_root() -> None:
    """Subtree pruning removes node ids from clean tree; LLM widgetIr must not hard-fail."""
    root = _screen_root()
    widget = ExtractedWidget(
        widget_name="Group17Widget",
        code="class Group17Widget extends StatelessWidget { const Group17Widget({super.key}); @override Widget build(BuildContext c) => const SizedBox.shrink(); }",
        widget_ir=WidgetIrNode(figma_id="1:3665", kind=WidgetIrKind.STACK),
    )
    validate_extracted_widget_ir(widget, root)


def test_realign_misplaced_ir_child_to_clean_parent() -> None:
    """LLM hoisted a leaf under the screen root; realign nests it under the clean parent."""
    frame = CleanDesignTreeNode(
        id="frame",
        name="Frame",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="leaf", name="Label", type=NodeType.TEXT, text="Hi"),
        ],
    )
    root = _screen_root().model_copy(update={"children": [frame]})
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(figma_id="leaf", kind=WidgetIrKind.TEXT),
            ],
        ),
    )
    moved = realign_screen_ir_children_to_clean_tree(screen_ir, root)
    assert moved == 1
    frame_ir = next(c for c in screen_ir.root.children if c.figma_id == "frame")
    assert frame_ir.kind == WidgetIrKind.COLUMN
    assert frame_ir.children[0].figma_id == "leaf"
    validate_screen_ir(screen_ir, root)


def test_realign_iterates_after_subtree_reparent() -> None:
    """A host reparented after DFS passed it must still realign nested chat-row children."""
    col = CleanDesignTreeNode(
        id="col",
        name="Col",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="title", name="Title", type=NodeType.TEXT, text="Hi"),
        ],
    )
    stamp = CleanDesignTreeNode(
        id="stamp",
        name="Stamp",
        type=NodeType.TEXT,
        text="18 Mar",
    )
    card = CleanDesignTreeNode(
        id="card",
        name="Card",
        type=NodeType.ROW,
        children=[col, stamp],
    )
    branch = CleanDesignTreeNode(id="branch", name="Branch", type=NodeType.COLUMN, children=[])
    host = CleanDesignTreeNode(id="host", name="Host", type=NodeType.ROW, children=[card])
    root = _screen_root().model_copy(update={"children": [branch, host]})
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figmaId="branch",
                    kind=WidgetIrKind.COLUMN,
                    children=[
                        WidgetIrNode(
                            figmaId="host",
                            kind=WidgetIrKind.ROW,
                            children=[
                                WidgetIrNode(
                                    figmaId="card",
                                    kind=WidgetIrKind.ROW,
                                    children=[
                                        WidgetIrNode(
                                            figmaId="col",
                                            kind=WidgetIrKind.COLUMN,
                                            children=[
                                                WidgetIrNode(
                                                    figmaId="title",
                                                    kind=WidgetIrKind.TEXT,
                                                ),
                                                WidgetIrNode(
                                                    figmaId="stamp",
                                                    kind=WidgetIrKind.TEXT,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    )
    moved = realign_screen_ir_children_to_clean_tree(screen_ir, root)
    assert moved >= 2
    host_ir = next(c for c in screen_ir.root.children if c.figma_id == "host")
    card_ir = host_ir.children[0]
    col_ir = next(c for c in card_ir.children if c.figma_id == "col")
    assert {c.figma_id for c in card_ir.children} == {"col", "stamp"}
    assert [c.figma_id for c in col_ir.children] == ["title"]
    validate_screen_ir(screen_ir, root)


def test_realign_drops_child_under_extracted_host() -> None:
    root = _screen_root()
    instance = CleanDesignTreeNode(
        id="inst",
        name="Icon",
        type=NodeType.CONTAINER,
        children=[
            CleanDesignTreeNode(
                id="Iinst;4:1",
                name="Vector",
                type=NodeType.VECTOR,
            ),
        ],
    )
    root = root.model_copy(update={"children": [instance]})
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="inst",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name="IconWidget"),
                ),
                WidgetIrNode(figma_id="Iinst;4:1", kind=WidgetIrKind.AUTO),
            ],
        ),
    )
    realign_screen_ir_children_to_clean_tree(screen_ir, root)
    assert all(c.figma_id != "Iinst;4:1" for c in screen_ir.root.children)
    validate_screen_ir(screen_ir, root, extracted_widget_names=frozenset({"IconWidget"}))


def test_validate_accepts_row_host_promoted_to_stack_for_absolute_footer() -> None:
    """Auto-layout frames with ABSOLUTE overlays must expose a STACK ancestor."""
    from figma_flutter_agent.parser.layout import promote_flex_hosts_with_absolute_children

    root = CleanDesignTreeNode(
        id="frame",
        name="Screen",
        type=NodeType.ROW,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=390.0,
            height=844.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="content",
                name="Content",
                type=NodeType.COLUMN,
                sizing=Sizing(width=391.0, height=626.8),
            ),
            CleanDesignTreeNode(
                id="footer",
                name="BottomNavBar",
                type=NodeType.COLUMN,
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    vertical="BOTTOM",
                    top=738.0,
                    width=390.0,
                    height=106.0,
                ),
                sizing=Sizing(
                    width_mode=SizingMode.FIXED,
                    height_mode=SizingMode.FIXED,
                    width=390.0,
                    height=106.0,
                ),
            ),
        ],
    )
    promoted = promote_flex_hosts_with_absolute_children(root)
    assert promoted.type == NodeType.STACK
    validate_screen_ir(default_screen_ir(promoted), promoted)


def test_validate_pin_bottom_chrome_rejects_unbounded_fixed_stack() -> None:
    from figma_flutter_agent.generator.ir.validate.guards import validate_render_safety

    nav = CleanDesignTreeNode(
        id="nav",
        name="Nav Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, width_mode=SizingMode.FIXED),
        stack_placement=StackPlacement(top=0.0, width=375.0),
        children=[
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="Title",
                stack_placement=StackPlacement(left=0.0, top=19.5, height=17.0),
            ),
        ],
    )
    body = CleanDesignTreeNode(
        id="body",
        name="Body",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=500.0),
        stack_placement=StackPlacement(top=56.0, width=375.0, height=500.0),
        children=[
            CleanDesignTreeNode(id="a", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(
                id="b",
                name="B",
                type=NodeType.COLUMN,
                children=[],
            ),
        ],
    )
    action = CleanDesignTreeNode(
        id="action",
        name="Action",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=80.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=80.0),
        children=[],
    )
    root = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[nav, body, action],
    )
    with pytest.raises(GenerationError, match="stack_bounded_in_scroll_viewport"):
        validate_render_safety(root)
