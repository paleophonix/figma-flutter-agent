"""Verbatica player emit-law regressions (decomposed flex, opacity, glyphs, progress)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.file_methods import (
    method_node_suppresses_compose_flex_fill,
    strip_top_level_flex_parent_data,
)
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.layout.widgets.finalize import _wrap_zero_opacity
from figma_flutter_agent.parser.interaction.icons import (
    is_private_use_area_glyph,
    private_use_glyph_icon_expr,
)
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def _phone_shell_column(*children: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="shell",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=393.0, height=852.0),
        children=list(children),
    )


def _growable_body_column() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="body",
        name="Body",
        type=NodeType.COLUMN,
        spacing=48.0,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FILL,
            width=393.0,
            height=610.0,
        ),
        alignment=Alignment(main="spaceBetween", cross="center"),
        children=[
            CleanDesignTreeNode(
                id="body-top",
                name="Top",
                type=NodeType.COLUMN,
                sizing=Sizing(width=393.0, height=300.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="body-bottom",
                name="Bottom",
                type=NodeType.COLUMN,
                sizing=Sizing(width=393.0, height=200.0),
                children=[],
            ),
        ],
    )


def _single_child_fill_body_column() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="body",
        name="Feature",
        type=NodeType.COLUMN,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FILL,
            width=393.0,
            height=610.0,
        ),
        alignment=Alignment(main="spaceBetween", cross="center"),
        children=[
            CleanDesignTreeNode(
                id="body-only",
                name="Content",
                type=NodeType.COLUMN,
                sizing=Sizing(width=393.0, height=400.0),
                children=[],
            ),
        ],
    )


def test_single_child_fill_phone_shell_body_suppresses_top_level_expanded() -> None:
    """LAW-FLEX-DECOMPOSED-SLOT: single-child FILL columns still strip method Expanded."""
    shell = _phone_shell_column(
        CleanDesignTreeNode(
            id="nav",
            name="Nav",
            type=NodeType.COLUMN,
            sizing=Sizing(width=393.0, height=128.0),
            children=[],
        ),
        _single_child_fill_body_column(),
        CleanDesignTreeNode(
            id="footer",
            name="Footer",
            type=NodeType.COLUMN,
            sizing=Sizing(width=393.0, height=114.0),
            children=[],
        ),
    )
    body = _single_child_fill_body_column()
    assert method_node_suppresses_compose_flex_fill(body, shell)


def test_decomposed_growable_slot_suppresses_top_level_expanded() -> None:
    """LAW-FLEX-DECOMPOSED-SLOT: compose owns flex fill for phone-shell body methods."""
    shell = _phone_shell_column(
        CleanDesignTreeNode(
            id="nav",
            name="Status bar",
            type=NodeType.COLUMN,
            sizing=Sizing(width=393.0, height=128.0),
            stack_placement=StackPlacement(vertical="TOP", width=393.0, height=128.0),
            children=[],
        ),
        _growable_body_column(),
        CleanDesignTreeNode(
            id="footer",
            name="Home indicator",
            type=NodeType.COLUMN,
            sizing=Sizing(width=393.0, height=114.0),
            stack_placement=StackPlacement(vertical="BOTTOM", width=393.0, height=114.0),
            children=[],
        ),
    )
    body = _growable_body_column()
    assert method_node_suppresses_compose_flex_fill(body, shell)
    emitted = render_node_body(
        body,
        is_layout_root=False,
        parent_type=NodeType.COLUMN,
        parent_node=shell,
        uses_svg=False,
    )
    assert emitted.lstrip().startswith("Expanded(")
    stripped = strip_top_level_flex_parent_data(emitted)
    assert not stripped.lstrip().startswith("Expanded(")
    assert stripped.lstrip().startswith("Column(")


def test_zero_opacity_frame_emits_shrink() -> None:
    """Fully transparent Figma frames must not paint or retain hit targets."""
    node = CleanDesignTreeNode(
        id="hidden",
        name="Leading",
        type=NodeType.ROW,
        style=NodeStyle(opacity=0.0),
        sizing=Sizing(width=71.0, height=44.0),
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Back",
                type=NodeType.TEXT,
                text="Back",
                sizing=Sizing(width=40.0, height=19.0),
            )
        ],
    )
    wrapped = _wrap_zero_opacity(node, "Text('Back')")
    assert wrapped == "const SizedBox.shrink()"


def test_supplementary_private_use_close_glyph_emits_material_icon() -> None:
    """Supplementary-plane SF Symbol dismiss glyphs map to Icons.close."""
    glyph = "\U000F015E"
    assert is_private_use_area_glyph(glyph)
    host = CleanDesignTreeNode(
        id="close-host",
        name="Close",
        type=NodeType.STACK,
        sizing=Sizing(width=30.0, height=30.0),
        style=NodeStyle(border_radius=15.0),
        children=[],
    )
    text = CleanDesignTreeNode(
        id="glyph",
        name="Glyph",
        type=NodeType.TEXT,
        text=glyph,
        sizing=Sizing(width=16.0, height=16.0),
        style=NodeStyle(text_color="0xFF6B48A3", font_size=16.0),
    )
    expr = private_use_glyph_icon_expr(text, parent_node=host)
    assert expr is not None
    assert "Icons.close" in expr
    body = render_node_body(
        text,
        parent_type=NodeType.STACK,
        parent_node=host,
        uses_svg=False,
    )
    assert "Icons.close" in body
    assert glyph not in body


def test_private_use_chevron_glyph_emits_material_icon() -> None:
    """Supplementary-plane SF Symbol chevrons map to Icons.chevron_right."""
    glyph = "\U000F018A"
    assert is_private_use_area_glyph(glyph)
    host = CleanDesignTreeNode(
        id="chevron-host",
        name="Chevron",
        type=NodeType.STACK,
        sizing=Sizing(width=8.0, height=32.0),
        children=[],
    )
    text = CleanDesignTreeNode(
        id="glyph",
        name="Glyph",
        type=NodeType.TEXT,
        text=glyph,
        sizing=Sizing(width=8.0, height=22.0),
        style=NodeStyle(text_color="0xFF8459C9", font_size=17.0),
    )
    expr = private_use_glyph_icon_expr(text, parent_node=host)
    assert expr is not None
    assert "Icons.chevron_right" in expr


def test_filled_vector_paint_fallback_emits_circle_and_play_icon() -> None:
    """Filled VECTOR leaves without exports emit primitive paint fallbacks."""
    from figma_flutter_agent.generator.layout.widgets.decoration import (
        _render_stroke_glyph_fallback,
    )

    thumb = CleanDesignTreeNode(
        id="thumb",
        name="Ellipse",
        type=NodeType.VECTOR,
        sizing=Sizing(width=20.0, height=20.0),
        style=NodeStyle(background_color="0xFF8459C9"),
    )
    play = CleanDesignTreeNode(
        id="play",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=22.0, height=28.0),
        style=NodeStyle(background_color="0xFFFFFFFF"),
    )
    thumb_expr = _render_stroke_glyph_fallback(thumb)
    play_expr = _render_stroke_glyph_fallback(play)
    assert thumb_expr is not None
    assert "BoxDecoration" in thumb_expr
    assert play_expr is not None
    assert "Icons.play_arrow" in play_expr


def test_center_pinned_nav_title_widens_explicit_lane() -> None:
    """Center-pinned nav titles widen when Figma intrinsic width underfits copy."""
    from figma_flutter_agent.generator.geometry.text_metrics import (
        center_pinned_text_explicit_lane_width,
    )

    title = CleanDesignTreeNode(
        id="title",
        name="Title",
        type=NodeType.TEXT,
        text="Урок 1",
        sizing=Sizing(width=49.0, height=19.0),
        style=NodeStyle(font_size=16.0, font_weight="w600", text_align="CENTER"),
        stack_placement=StackPlacement(
            horizontal="CENTER",
            left=173.0,
            right=171.0,
            top=12.5,
            width=49.0,
            height=19.0,
        ),
    )
    lane = center_pinned_text_explicit_lane_width(
        title,
        title.stack_placement,
        parent_width=393.0,
    )
    assert lane is not None
    assert lane > 49.0


def test_private_use_close_glyph_emits_material_icon() -> None:
    """Private-use SF Symbol text in compact dismiss hosts maps to Icons.close."""
    glyph = "\uf8ff"
    assert is_private_use_area_glyph(glyph)
    host = CleanDesignTreeNode(
        id="close-host",
        name="Close",
        type=NodeType.STACK,
        sizing=Sizing(width=30.0, height=30.0),
        style=NodeStyle(border_radius=15.0),
        children=[],
    )
    text = CleanDesignTreeNode(
        id="glyph",
        name="Glyph",
        type=NodeType.TEXT,
        text=glyph,
        sizing=Sizing(width=16.0, height=16.0),
        style=NodeStyle(text_color="0xFF6B48A3", font_size=16.0),
    )
    expr = private_use_glyph_icon_expr(text, parent_node=host)
    assert expr is not None
    assert "Icons.close" in expr
    body = render_node_body(
        text,
        parent_type=NodeType.STACK,
        parent_node=host,
        uses_svg=False,
    )
    assert "Icons.close" in body
    assert glyph not in body


def test_mixed_progress_stack_positions_inflow_segment_from_geometry() -> None:
    """Horizontal progress segments share one coordinate frame via geometry pins."""
    filled = CleanDesignTreeNode(
        id="filled",
        name="Filled",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=194.0, height=2.0),
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=24.0, y=8.0, width=194.0, height=2.0),
        ),
        style=NodeStyle(background_color="0xFF8459C9"),
    )
    track = CleanDesignTreeNode(
        id="track",
        name="Track",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=148.0, height=2.0),
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(left=218.0, top=8.0, width=148.0, height=2.0),
        style=NodeStyle(background_color="0x1719191A"),
    )
    progress = CleanDesignTreeNode(
        id="progress",
        name="Progress",
        type=NodeType.STACK,
        padding={"top": 8.0, "bottom": 8.0, "left": 24.0, "right": 24.0},
        spacing=4.0,
        sizing=Sizing(width=390.0, height=18.0),
        children=[filled, track],
    )
    body = render_node_body(progress, uses_svg=False)
    compact = body.replace(" ", "")
    assert "Positioned(left:24.0" in compact
    assert "Positioned(left:218.0" in compact


def test_button_group_opacity_not_duplicated_on_extracted_ref() -> None:
    """Extracted widget refs must not receive an outer Opacity wrapper at call sites."""
    from figma_flutter_agent.generator.layout.widgets.finalize import _wrap_group_opacity

    node = CleanDesignTreeNode(
        id="btn",
        name="Button",
        type=NodeType.BUTTON,
        extracted_widget_ref="VerifyButtonWidget",
        style=NodeStyle(opacity=0.5, background_color="0xFF8459C9"),
        sizing=Sizing(width=361.0, height=56.0),
        children=[],
    )
    wrapped = _wrap_group_opacity(node, "const VerifyButtonWidget()")
    assert wrapped == "const VerifyButtonWidget()"
