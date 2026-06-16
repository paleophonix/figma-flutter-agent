"""Tests for lazy scroll list section extent binding."""

from figma_flutter_agent.generator.layout.scroll import render_scroll_list
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_listview_builder_boxes_stack_section_with_finite_height() -> None:
    """Vertical lazy list items must bind band height before absolute Stack emit."""
    header_band = CleanDesignTreeNode(
        id="header",
        name="Header",
        type=NodeType.STACK,
        sizing=Sizing(width=117.0, height=45.0),
        stack_placement=StackPlacement(width=117.0, height=45.0),
        children=[
            CleanDesignTreeNode(id="title", name="Title", type=NodeType.TEXT, text="Details"),
        ],
    )
    node = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        children=[
            header_band,
            *[
                CleanDesignTreeNode(id=f"c{i}", name=f"Item {i}", type=NodeType.TEXT, text=str(i))
                for i in range(7)
            ],
        ],
    )
    children = [
        "Stack(clipBehavior: Clip.none, children: [Positioned(left: 0.0, top: 0.0, child: Text('Details'))])",
        *[f"Text('{i}')" for i in range(7)],
    ]

    widget = render_scroll_list(
        node,
        children,
        axis="vertical",
        parent_type=None,
        section_children=node.children,
    )

    assert "ListView.builder(" in widget
    assert "return Stack(" not in widget
    assert "height: 45.0" in widget
    assert "return Expanded(" not in widget


def test_listview_builder_strips_nested_flexible_from_footer_like_item() -> None:
    """Deep flex strip removes nested Flexible wrappers from scroll items."""
    footer = CleanDesignTreeNode(
        id="footer",
        name="Footer",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=184.0),
    )
    node = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        children=[
            CleanDesignTreeNode(id=f"c{i}", name=f"Item {i}", type=NodeType.TEXT, text=str(i))
            for i in range(8)
        ]
        + [footer],
    )
    children = [
        *[f"Text('{i}')" for i in range(8)],
        (
            "Align(child: SizedBox(width: double.infinity, child: Stack(children: ["
            "SizedBox(height: 184.0, child: Flexible(fit: FlexFit.loose, flex: 0, child: Text('bg'))), "
            "Text('cta')]))))"
        ),
    ]

    widget = render_scroll_list(
        node,
        children,
        axis="vertical",
        parent_type=None,
        section_children=node.children,
    )

    assert "Flexible(" not in widget
    assert "height: 184.0" in widget


def test_listview_boxes_stack_when_nested_positioned_has_height() -> None:
    """Nested Positioned heights must not skip outer scroll-item boxing."""
    header_band = CleanDesignTreeNode(
        id="header",
        name="Header",
        type=NodeType.STACK,
        sizing=Sizing(width=117.0, height=45.0),
        children=[
            CleanDesignTreeNode(id="title", name="Title", type=NodeType.TEXT, text="Details"),
            CleanDesignTreeNode(id="back", name="Back", type=NodeType.BUTTON, text="Back"),
        ],
    )
    node = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        children=[
            header_band,
            *[
                CleanDesignTreeNode(id=f"c{i}", name=f"Item {i}", type=NodeType.TEXT, text=str(i))
                for i in range(8)
            ],
        ],
    )
    children = [
        (
            "Stack(clipBehavior: Clip.none, children: ["
            "Positioned(left: 61.0, top: 12.0, width: 78.6, child: Text('Details')), "
            "Positioned(left: 0.0, bottom: 0.0, width: 45.0, height: 45.0, child: Text('back'))"
            "])"
        ),
        *[f"Text('{i}')" for i in range(8)],
    ]

    widget = render_scroll_list(
        node,
        children,
        axis="vertical",
        parent_type=None,
        section_children=node.children,
    )

    flat = widget.replace("\n", " ")
    assert "ListView.builder(" in widget
    assert "if (index == 0) return SizedBox(" in flat
    assert "height: 45.0" in widget
    assert "if (index == 0) return Stack(" not in flat


def test_listview_boxes_width_only_stack_child_with_inner_height() -> None:
    """Width-only SizedBox around Stack must gain recovered band height."""
    hero_band = CleanDesignTreeNode(
        id="hero",
        name="Hero",
        type=NodeType.STACK,
        sizing=Sizing(width=327.0, height=184.0),
    )
    node = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        children=[
            hero_band,
            *[
                CleanDesignTreeNode(id=f"c{i}", name=f"Item {i}", type=NodeType.TEXT, text=str(i))
                for i in range(8)
            ],
        ],
    )
    children = [
        (
            "SizedBox(width: double.infinity, child: Stack(fit: StackFit.expand, "
            "clipBehavior: Clip.none, children: ["
            "Positioned.fill(child: SizedBox(width: 327.0, height: 184.0, child: Text('hero')))"
            "]))"
        ),
        *[f"Text('{i}')" for i in range(8)],
    ]

    widget = render_scroll_list(
        node,
        children,
        axis="vertical",
        parent_type=None,
        section_children=node.children,
    )

    flat = widget.replace("\n", " ")
    assert "ListView.builder(" in widget
    assert "if (index == 0) return SizedBox(" in flat
    assert "height: 184.0" in widget
    assert "if (index == 0) return Stack(" not in flat
