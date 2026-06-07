"""ROW flex allocation: FIXED peers must not steal space from FILL siblings."""

from figma_flutter_agent.generator.geometry.flex import compute_flex_deltas
from figma_flutter_agent.generator.layout.widgets.render import render_node_body
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    WrapKind,
)


def test_fixed_row_peer_omits_flexible_loose_when_constrained() -> None:
    avatar = CleanDesignTreeNode(
        id="1:avatar",
        name="Avatar",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=80.0, height=80.0),
    )
    details = CleanDesignTreeNode(
        id="1:details",
        name="Details",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=112.0),
        children=[
            CleanDesignTreeNode(
                id="1:text",
                name="Hint",
                type=NodeType.TEXT,
                text="Caption",
                style=NodeStyle(font_size=14.0),
            )
        ],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=112.0),
        spacing=16.0,
        children=[avatar, details],
    )
    wraps, _ = compute_flex_deltas(row, avatar)
    assert WrapKind.CONSTRAINED_BOX in wraps
    assert WrapKind.FLEXIBLE_LOOSE not in wraps
    assert WrapKind.EXPANDED not in wraps


def test_nested_fixed_row_avatar_peer_does_not_expand() -> None:
    """FIXED nested ROW (glyph badge shell) must not grow beside a FILL column."""
    avatar_shell = CleanDesignTreeNode(
        id="1:avatar-shell",
        name="Background",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=80.0, height=80.0),
        alignment=Alignment(main="center", cross="center"),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[
            CleanDesignTreeNode(
                id="1:glyph",
                name="Glyph",
                type=NodeType.TEXT,
                text="И",
                sizing=Sizing(width=19.0, height=36.0),
                style=NodeStyle(font_size=24.0, font_weight="w700"),
            )
        ],
    )
    details = CleanDesignTreeNode(
        id="1:details",
        name="Details",
        type=NodeType.COLUMN,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FILL,
            width=221.0,
            height=112.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:hint",
                name="Hint",
                type=NodeType.TEXT,
                text="Caption",
                sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=48.0),
                style=NodeStyle(font_size=14.0),
            ),
            CleanDesignTreeNode(
                id="1:btn",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=52.0),
            ),
        ],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=112.0),
        children=[avatar_shell, details],
    )
    body = render_node_body(row, uses_svg=False)
    compact = body.replace("\n", "")
    assert compact.count("Expanded(child:") == 1
    assert "width: 80.0" in compact
    assert "width: 221.0" in compact


def test_fill_row_fixed_plus_fill_emits_non_flex_fixed_peer() -> None:
    details = CleanDesignTreeNode(
        id="1:details",
        name="Details",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=112.0),
        children=[
            CleanDesignTreeNode(
                id="1:hint",
                name="Hint",
                type=NodeType.TEXT,
                text="Caption line one\nCaption line two",
                sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=48.0),
                style=NodeStyle(font_size=14.0),
            ),
            CleanDesignTreeNode(
                id="1:btn",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=52.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:label",
                        name="Label",
                        type=NodeType.TEXT,
                        text="Update avatar",
                        style=NodeStyle(font_size=14.0),
                    )
                ],
            ),
        ],
    )
    avatar = CleanDesignTreeNode(
        id="1:avatar",
        name="Avatar",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=80.0, height=80.0),
        style=NodeStyle(background_color="0xFFEEF9F0"),
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=112.0),
        children=[avatar, details],
    )
    body = render_node_body(row, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Expanded(child:" in compact
    assert "Flexible(fit: FlexFit.loose, child: SizedBox(width: 80.0" not in compact
    assert "width: 80.0" in compact
