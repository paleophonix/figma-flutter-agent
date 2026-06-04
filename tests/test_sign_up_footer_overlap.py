"""Footer link must sit below the full primary SIGN UP pill, not collapse the fill."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.generator.layout_widget import (
    _render_centered_figma_text_lines,
    render_node_body,
)
from figma_flutter_agent.parser.interaction import stack_interaction_kind
from figma_flutter_agent.parser.layout import (
    reconcile_cta_footer_surfaces_in_tree,
    reconcile_logo_wordmark_top_in_tree,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def _silent_moon_cta_row() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:3970",
        name="Button row",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=97.0),
        stack_placement=StackPlacement(left=20.0, top=700.0, width=374.0, height=97.0),
        children=[
            CleanDesignTreeNode(
                id="1:3971",
                name="Fill",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=374.0, height=63.0),
                style=NodeStyle(background_color="0xFF8E97FD", border_radius=38.0),
                stack_placement=StackPlacement(bottom=34.0, width=374.0, height=63.0),
            ),
            CleanDesignTreeNode(
                id="1:3972",
                name="SIGN UP",
                type=NodeType.TEXT,
                text="SIGN UP",
                stack_placement=StackPlacement(left=156.0, top=25.0, width=62.0, height=14.0),
            ),
            CleanDesignTreeNode(
                id="1:3973",
                name="Footer",
                type=NodeType.TEXT,
                text="ALREADY HAVE AN ACCOUNT?",
                stack_placement=StackPlacement(left=46.0, top=39.0, width=282.0, height=14.0),
            ),
        ],
    )


def test_cta_row_with_footer_is_not_single_button_stack() -> None:
    row = _silent_moon_cta_row()
    assert stack_interaction_kind(row) is None


def test_reconcile_moves_footer_below_full_cta_surface() -> None:
    row = reconcile_cta_footer_surfaces_in_tree(_silent_moon_cta_row())
    surface = row.children[0]
    footer = row.children[2]
    assert surface.sizing.height == 63.0
    assert footer.stack_placement is not None
    assert footer.stack_placement.top is not None
    assert footer.stack_placement.top >= 67.0


def test_footer_render_uses_full_pill_height() -> None:
    row = reconcile_cta_footer_surfaces_in_tree(_silent_moon_cta_row())
    body = render_node_body(row, uses_svg=False)
    assert "height: 63.0" in body
    assert "ALREADY HAVE AN ACCOUNT?" in body
    assert "height: 35.0" not in body
    assert "Positioned(left: 0.0, top: 0.0" in body
    assert "textAlign: TextAlign.center" in body
    assert "Alignment.center" in body


def test_logo_wordmark_gets_minimum_top_inset() -> None:
    logo = CleanDesignTreeNode(
        id="logo",
        name="Brand",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=36.0),
        stack_placement=StackPlacement(left=107.0, top=18.0, width=200.0, height=36.0),
        children=[
            CleanDesignTreeNode(
                id="t1",
                name="Silent",
                type=NodeType.TEXT,
                text="Silent",
                sizing=Sizing(width=60.0, height=20.0),
            ),
            CleanDesignTreeNode(
                id="icon",
                name="Icon",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/moon.svg",
                sizing=Sizing(width=24.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="t2",
                name="Moon",
                type=NodeType.TEXT,
                text="Moon",
                sizing=Sizing(width=60.0, height=20.0),
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[logo],
    )
    updated = reconcile_logo_wordmark_top_in_tree(screen)
    assert updated.children[0].stack_placement is not None
    assert updated.children[0].stack_placement.top == 56.0


def test_flattened_logo_svg_gets_minimum_top_inset() -> None:
    logo = CleanDesignTreeNode(
        id="1:3665",
        name="Group 17",
        type=NodeType.STACK,
        sizing=Sizing(width=168.0, height=30.0),
        stack_placement=StackPlacement(left=123.0, top=6.0, width=168.0, height=30.0),
        vector_asset_key="assets/illustrations/group_17.svg",
        render_boundary=True,
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[logo],
    )
    updated = reconcile_logo_wordmark_top_in_tree(screen)
    assert updated.children[0].stack_placement is not None
    assert updated.children[0].stack_placement.top == 56.0


def test_centered_subtitle_with_explicit_newlines_uses_column_per_line() -> None:
    subtitle = CleanDesignTreeNode(
        id="1:3976",
        name="Subtitle",
        type=NodeType.TEXT,
        text="Thousand of people are usign silent moon\nfor smalls meditation",
        style=NodeStyle(text_align="CENTER", font_size=16.0),
    )
    widget = _render_centered_figma_text_lines(
        subtitle,
        style_expr="Theme.of(context).textTheme.titleMedium",
        text_align_suffix=", textAlign: TextAlign.center",
    )
    assert widget is not None
    assert widget.startswith("Column(")
    assert "softWrap: false" in widget
    assert "maxLines: 1" in widget
    assert "silent moon" in widget
    assert "for smalls meditation" in widget


def test_silent_moon_layout_footer_below_cta_band() -> None:
    row = reconcile_cta_footer_surfaces_in_tree(_silent_moon_cta_row())
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[row],
    )
    files = render_layout_file(screen, feature_name="welcome", uses_svg=False)
    layout = files["lib/generated/welcome_layout.dart"]
    assert "height: 63.0" in layout
    footer_idx = layout.index("ALREADY HAVE AN ACCOUNT?")
    pill_idx = layout.index("height: 63.0")
    assert pill_idx < footer_idx
