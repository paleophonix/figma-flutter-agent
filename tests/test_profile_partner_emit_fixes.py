"""Regression guards for profile-style metric pills, chips, nav, and icon rails."""

from figma_flutter_agent.generator.layout.flex_policy import (
    column_center_hug_child_wrap,
)
from figma_flutter_agent.generator.layout.navigation import bottom_nav_stateful_helpers
from figma_flutter_agent.generator.layout.style import border_radius_expr
from figma_flutter_agent.generator.layout.widgets.render import render_node_body
from figma_flutter_agent.generator.renderer_theme import resolve_theme_font_family
from figma_flutter_agent.parser.interaction import list_tile_leading_icon_slot
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
)


def test_resolve_theme_font_family_prefers_branded_font_over_roboto() -> None:
    assert resolve_theme_font_family(["Golos Text", "Roboto"]) == "Golos Text"


def test_border_radius_expr_clamps_figma_pill_tokens() -> None:
    style = NodeStyle(border_radius=35_791_400.0)
    expr = border_radius_expr(style, frame_height=38.0)
    assert "19.0" in expr
    assert "35791400" not in expr


def test_centered_metric_label_uses_full_column_width() -> None:
    parent = CleanDesignTreeNode(
        id="1:col",
        name="Column",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=100.0),
        alignment=Alignment(cross="center"),
    )
    child = CleanDesignTreeNode(
        id="1:label",
        name="Label",
        type=NodeType.COLUMN,
        sizing=Sizing(width=40.0, height=20.0),
        children=[
            CleanDesignTreeNode(
                id="1:text",
                name="Metric",
                type=NodeType.TEXT,
                text="Скидка",
                style=NodeStyle(text_align="CENTER", font_size=12.0),
            )
        ],
    )
    wrapped = column_center_hug_child_wrap(
        parent,
        child,
        "Text('Скидка', textAlign: TextAlign.center)",
    )
    assert "width: double.infinity" in wrapped
    assert "width: 40.0" not in wrapped


def test_bottom_nav_helpers_keep_bar_when_height_is_bounded() -> None:
    helpers = bottom_nav_stateful_helpers(node_id="1:nav")
    assert "constraints.maxHeight > 120.0" in helpers


def test_list_tile_leading_icon_slot_detects_first_row_child() -> None:
    icon = CleanDesignTreeNode(
        id="1:icon",
        name="Background",
        type=NodeType.ROW,
        sizing=Sizing(width=48.0, height=48.0),
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        children=[
            icon,
            CleanDesignTreeNode(
                id="1:text",
                name="Copy",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, width=200.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:title",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Чаты",
                    ),
                    CleanDesignTreeNode(
                        id="1:sub",
                        name="Subtitle",
                        type=NodeType.TEXT,
                        text="Поддержка",
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="1:chev",
                name="Chevron",
                type=NodeType.STACK,
                sizing=Sizing(width=20.0, height=20.0),
            ),
        ],
    )
    assert list_tile_leading_icon_slot(icon, row, parent_type=NodeType.ROW)


def test_pill_label_row_hugs_text_width() -> None:
    pill = CleanDesignTreeNode(
        id="1:pill",
        name="Badge",
        type=NodeType.ROW,
        padding={"left": 12.0, "right": 12.0, "top": 4.0, "bottom": 4.0},
        sizing=Sizing(width=168.0, height=25.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=99.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Личный кабинет партнера",
                style=NodeStyle(
                    text_color="0xFF2E7D32",
                    font_size=12.0,
                    font_weight="w600",
                ),
            )
        ],
    )
    body = render_node_body(pill, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "mainAxisSize: MainAxisSize.min" in compact
    assert "width: 168.0" not in compact


def test_list_tile_leading_without_asset_falls_back_to_material_icon() -> None:
    text_col = CleanDesignTreeNode(
        id="1:text",
        name="Copy",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=200.0),
        children=[
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Чаты",
            ),
            CleanDesignTreeNode(
                id="1:sub",
                name="Subtitle",
                type=NodeType.TEXT,
                text="Поддержка",
            ),
        ],
    )
    icon = CleanDesignTreeNode(
        id="1:icon",
        name="Background",
        type=NodeType.ROW,
        cluster_id="cluster-bg",
        sizing=Sizing(width=48.0, height=48.0),
    )
    button = CleanDesignTreeNode(
        id="1:btn",
        name="Button",
        type=NodeType.BUTTON,
        spacing=12.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=329.0, height=80.0),
        children=[
            icon,
            text_col,
            CleanDesignTreeNode(
                id="1:chev",
                name="Chevron",
                type=NodeType.STACK,
                sizing=Sizing(width=20.0, height=20.0),
            ),
        ],
    )
    body = render_node_body(
        icon,
        uses_svg=True,
        parent_type=NodeType.BUTTON,
        parent_node=button,
        cluster_classes={"cluster-bg": "BackgroundWidget"},
    )
    assert "BackgroundWidget" not in body
    assert "Icons.chat_bubble_outline" in body


def test_square_icon_rail_svg_clamps_to_glyph_size() -> None:
    vector = CleanDesignTreeNode(
        id="1:vector",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=48.0, height=48.0),
        vector_asset_key="assets/icons/profile_contact.svg",
    )
    body = render_node_body(vector, uses_svg=True, parent_type=NodeType.ROW)
    assert "width: 20.0" in body
    assert "width: 48.0" not in body.split("SvgPicture.asset")[1][:120]
