"""Laws for ROW fill-width text: Expanded stretch, no infinite width under loose flex."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.tree import default_screen_ir, index_clean_tree
from figma_flutter_agent.generator.ir.validate import _apply_row_text_flex_guard, apply_ir_guards
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    FlexWrapIr,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
    WidgetIrNode,
)


def _section_header_title_row() -> CleanDesignTreeNode:
    title = CleanDesignTreeNode(
        id="hdr:title",
        name="section_header",
        type=NodeType.TEXT,
        text="Section Header",
        sizing=Sizing(width=268.0, height=24.0, width_mode=SizingMode.FILL),
        style=NodeStyle(text_align="LEFT", font_size=18.0, font_weight="w600"),
    )
    action = CleanDesignTreeNode(
        id="hdr:action",
        name="action_group",
        type=NodeType.ROW,
        spacing=8.0,
        sizing=Sizing(width=74.0, height=36.0),
        children=[
            CleanDesignTreeNode(
                id="hdr:button",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width=74.0, height=36.0),
            ),
        ],
    )
    return CleanDesignTreeNode(
        id="hdr:row",
        name="Section Header",
        type=NodeType.ROW,
        spacing=16.0,
        padding=Padding(top=12.0, bottom=12.0, left=16.0, right=16.0),
        sizing=Sizing(width=390.0, height=72.0, width_mode=SizingMode.FILL),
        alignment=Alignment(cross="center"),
        children=[title, action],
    )


def _find_ir_node(node: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if node.figma_id == figma_id:
        return node
    for child in node.children:
        found = _find_ir_node(child, figma_id)
        if found is not None:
            return found
    return None


def test_row_fill_left_text_emits_expanded_without_infinite_width() -> None:
    """Law: row_flex_child_must_not_force_infinite_width."""
    row = _section_header_title_row()
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "Expanded(child:" in compact
    assert "Section Header" in body
    assert "Flexible(fit: FlexFit.loose, flex: 0" not in compact


def test_ir_guard_upgrades_row_fill_text_flexible_loose_to_expanded() -> None:
    """Law: row_fill_text_must_emit_expanded_not_flexible_loose."""
    row = _section_header_title_row()
    tree_by_id = index_clean_tree(row)
    parent_by_id = {child.id: row.id for child in row.children}
    ir_node = WidgetIrNode(figmaId="hdr:title", wrap=FlexWrapIr.FLEXIBLE_LOOSE)
    _apply_row_text_flex_guard(
        ir_node,
        tree_by_id["hdr:title"],
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    )
    assert ir_node.wrap == FlexWrapIr.EXPANDED


def test_ir_guard_preserves_flexible_loose_for_row_hug_text() -> None:
    row = _section_header_title_row()
    title = row.children[0].model_copy(
        update={"sizing": Sizing(width=120.0, height=24.0, width_mode=SizingMode.HUG)},
    )
    tree_by_id = index_clean_tree(row)
    parent_by_id = {title.id: row.id}
    tree_by_id[title.id] = title
    ir_node = WidgetIrNode(figmaId=title.id)
    _apply_row_text_flex_guard(
        ir_node,
        title,
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    )
    assert ir_node.wrap == FlexWrapIr.FLEXIBLE_LOOSE


def test_apply_ir_guards_row_fill_text_end_to_end() -> None:
    row = _section_header_title_row()
    screen_ir = default_screen_ir(row)
    title_ir = _find_ir_node(screen_ir.root, "hdr:title")
    assert title_ir is not None
    title_ir.wrap = FlexWrapIr.FLEXIBLE_LOOSE
    apply_ir_guards(screen_ir, row)
    updated = _find_ir_node(screen_ir.root, "hdr:title")
    assert updated is not None
    assert updated.wrap == FlexWrapIr.EXPANDED
