"""Regression tests for gist-class field/nav/badge emit laws."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.ir.extracted import _preserve_extracted_widget_decoration_shell
from figma_flutter_agent.generator.layout.flex_policy.stack import layout_fact_icon_badge_stack
from figma_flutter_agent.generator.layout.form import render_dropdown
from figma_flutter_agent.generator.layout.navigation.items import collect_bottom_nav_items
from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.generator.layout.widgets.finalize import _wrap_min_touch_target
from figma_flutter_agent.generator.layout.widgets.position import (
    placement_dual_horizontal_insets_overconstrain,
)
from figma_flutter_agent.generator.layout.widgets.text import _apply_stack_position
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GeomRect,
    GeometryFrame,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GIST_PROCESSED = _REPO_ROOT / ".debug" / "screen" / "limbo" / "gist_add_expenses_945" / "processed.json"


def _load_gist_tree() -> CleanDesignTreeNode | None:
    if not _GIST_PROCESSED.is_file():
        return None
    payload = json.loads(_GIST_PROCESSED.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload["cleanTree"])


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def _find_parent(
    root: CleanDesignTreeNode,
    node_id: str,
    parent: CleanDesignTreeNode | None = None,
) -> tuple[CleanDesignTreeNode | None, CleanDesignTreeNode | None]:
    if root.id == node_id:
        return parent, root
    for child in root.children:
        found_parent, found = _find_parent(child, node_id, root)
        if found is not None:
            return found_parent, found
    return None, None


def test_center_overconstrained_placement_prefers_layout_rect_edges() -> None:
    """CENTER anchor left+right must not produce negative width when overconstrained."""
    placement = StackPlacement(
        horizontal="CENTER",
        vertical="TOP",
        left=197.0,
        right=330.0,
        width=36.0,
        height=23.0,
    )
    assert placement_dual_horizontal_insets_overconstrain(placement, 393.0)
    label = CleanDesignTreeNode(
        id="label",
        name="Date",
        type=NodeType.TEXT,
        text="Date",
        sizing=Sizing(width=36.0, height=23.0),
        stack_placement=placement,
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=64.0, y=175.0, width=36.0, height=23.0),
        ),
    )
    parent = CleanDesignTreeNode(
        id="screen",
        name="screen",
        type=NodeType.STACK,
        sizing=Sizing(width=393.0, height=900.0),
    )
    positioned = _apply_stack_position(
        label,
        "Text('Date')",
        parent_type=NodeType.STACK,
        parent_node=parent,
    )
    assert "left: 64.0" in positioned
    assert "width: 36.0" in positioned
    assert "right:" not in positioned


def test_vertical_center_corrupt_top_prefers_layout_rect_y() -> None:
    placement = StackPlacement(
        horizontal="RIGHT",
        vertical="TOP",
        right=36.0,
        top=451.0,
        width=30.0,
        height=30.0,
    )
    bell = CleanDesignTreeNode(
        id="bell",
        name="bell",
        type=NodeType.STACK,
        sizing=Sizing(width=30.0, height=30.0),
        stack_placement=placement,
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=327.0, y=61.0, width=30.0, height=30.0),
        ),
    )
    parent = CleanDesignTreeNode(
        id="screen",
        name="screen",
        type=NodeType.STACK,
        sizing=Sizing(width=393.0, height=900.0),
    )
    positioned = _apply_stack_position(
        bell,
        "IconNotificationWidget()",
        parent_type=NodeType.STACK,
        parent_node=parent,
    )
    assert "top: 61.0" in positioned
    assert "top: 451.0" not in positioned


def test_dropdown_field_host_keeps_width_and_chrome() -> None:
    dropdown = CleanDesignTreeNode(
        id="dropdown",
        name="category",
        type=NodeType.DROPDOWN,
        sizing=Sizing(width=320.0, height=41.0),
        style=NodeStyle(background_color="0xFFDFF7E2", border_radius=8.0),
        min_touch_target=44.0,
        children=[
            CleanDesignTreeNode(
                id="item",
                name="item",
                type=NodeType.TEXT,
                text="Select the category",
            )
        ],
    )
    emitted = render_dropdown(dropdown, theme_variant="material_3")
    wrapped = _wrap_min_touch_target(dropdown, emitted)
    assert "BoxDecoration(" in emitted
    assert "width: 320.0" in emitted
    assert "SizedBox(width: 44.0" not in wrapped


def test_icon_only_bottom_nav_tabs_resolve_without_stack_placement() -> None:
    tree = _load_gist_tree()
    if tree is None:
        return
    bottom_nav = _find_node(tree, "7420:7053")
    assert bottom_nav is not None
    items = collect_bottom_nav_items(bottom_nav)
    assert len(items) >= 2


def test_icon_badge_stack_emits_background_shell() -> None:
    tree = _load_gist_tree()
    if tree is None:
        badge = CleanDesignTreeNode(
            id="badge",
            name="calendar",
            type=NodeType.STACK,
            sizing=Sizing(width=23.7, height=22.0),
            children=[
                CleanDesignTreeNode(
                    id="surface",
                    name="surface",
                    type=NodeType.CONTAINER,
                    sizing=Sizing(width=23.7, height=22.0),
                    style=NodeStyle(background_color="0xFF00D09E", border_radius=9.1),
                ),
                CleanDesignTreeNode(
                    id="glyph",
                    name="glyph",
                    type=NodeType.VECTOR,
                    vector_asset_key="assets/icons/calendar.svg",
                    sizing=Sizing(width=13.1, height=11.6),
                ),
            ],
        )
    else:
        badge = _find_node(tree, "7110:3343")
        assert badge is not None
    assert layout_fact_icon_badge_stack(badge)
    emitted = render_node_body(badge, uses_svg=True, theme_variant="material_3")
    assert "BoxDecoration(" in emitted
    assert "SvgPicture" in emitted


def test_extracted_widget_preserves_host_decoration_shell() -> None:
    subtree = CleanDesignTreeNode(
        id="icon-host",
        name="notification",
        type=NodeType.STACK,
        sizing=Sizing(width=30.0, height=30.0),
        style=NodeStyle(background_color="0xFFDFF7E2", border_radius=15.0),
        children=[],
    )
    wrapped = _preserve_extracted_widget_decoration_shell(
        subtree,
        "SvgPicture.asset('assets/icons/bell.svg')",
    )
    assert "BoxDecoration(" in wrapped
    assert "width: 30.0" in wrapped
