"""Regression tests for food-menu avatar stack and trailing chevron emit laws."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.generator.layout.widgets.svg import _render_svg_picture
from figma_flutter_agent.generator.layout.widgets.thumbnail import (
    find_media_avatar_paint_substrate,
    try_render_compact_raster_photo_stack,
)
from figma_flutter_agent.parser.boundaries.assets import (
    _best_descendant_vector_asset,
    _vector_asset_discovery_rank,
)
from figma_flutter_agent.parser.interaction.icons import (
    layout_fact_stroke_chevron_vector,
    layout_fact_trailing_chevron_action_slot,
    trailing_chevron_glyph_paint_span,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def _profile_avatar_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="137:202",
        name="Profile",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        children=[
            CleanDesignTreeNode(
                id="137:203",
                name="Rectangle 1223",
                type=NodeType.VECTOR,
                sizing=Sizing(width=100.0, height=100.0),
                style=NodeStyle(background_color="0xFFFFC6AE", border_radius=170.0),
                vector_asset_key="assets/icons/rectangle_1223_137_203.svg",
            ),
            CleanDesignTreeNode(
                id="137:204",
                name="mask",
                type=NodeType.STACK,
                sizing=Sizing(width=100.0, height=100.0),
                children=[
                    CleanDesignTreeNode(
                        id="137:205",
                        name="Rectangle 1293",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=100.0, height=100.0),
                        style=NodeStyle(background_color="0xFF98A8B8", border_radius=150.0),
                        image_asset_key="assets/images/rectangle_1293_137_205.png",
                    ),
                ],
            ),
        ],
    )


def _trailing_chevron_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="152:36",
        name="chevron-right",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        stack_placement=StackPlacement(left=263.0, top=8.0, width=24.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="152:37",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=4.0, height=8.0),
                style=NodeStyle(has_stroke=True, border_width=1.5, border_color="0xFF747783"),
                vector_asset_key="assets/icons/vector_152_37.svg",
                geometry_frame=GeometryFrame(
                    intrinsic_size=GeomRect(width=4.0, height=8.0),
                    paint_rect=GeomRect(width=5.5, height=9.5),
                ),
            ),
        ],
    )


def test_media_avatar_paint_substrate_is_detected() -> None:
    host = _profile_avatar_stack()
    photo = host.children[1].children[0]
    substrate = find_media_avatar_paint_substrate(host, photo=photo)
    assert substrate is not None
    assert substrate.id == "137:203"


def test_media_avatar_stack_emits_substrate_before_raster_mask() -> None:
    emitted = try_render_compact_raster_photo_stack(_profile_avatar_stack(), uses_svg=True)
    assert emitted is not None
    assert "rectangle_1223_137_203.svg" in emitted
    assert "rectangle_1293_137_205.png" in emitted
    assert "Stack(fit: StackFit.expand" in emitted


def test_trailing_chevron_vector_is_recognized() -> None:
    chevron = _trailing_chevron_stack().children[0]
    assert layout_fact_stroke_chevron_vector(chevron)
    assert layout_fact_trailing_chevron_action_slot(_trailing_chevron_stack())


def test_trailing_chevron_glyph_uses_intrinsic_paint_bounds() -> None:
    host = _trailing_chevron_stack()
    span = trailing_chevron_glyph_paint_span(host)
    assert span is not None
    assert span[0] <= 6.0
    assert 7.0 <= span[1] <= 10.0


def test_trailing_chevron_svg_is_centered_in_action_slot() -> None:
    host = _trailing_chevron_stack()
    emitted = _render_svg_picture(host, "assets/icons/vector_152_37.svg")
    assert (
        "Center(child: SizedBox(width: 5.5" in emitted
        or "Center(child: SizedBox(width: 4.0" in emitted
    )
    assert "SizedBox(width: 24.0, height: 24.0" in emitted
    assert "SvgPicture.asset('assets/icons/vector_152_37.svg'" in emitted


def test_vector_asset_discovery_prefers_component_chevron_export() -> None:
    assert _vector_asset_discovery_rank("assets/icons/chevron-right_152_123.svg") < (
        _vector_asset_discovery_rank("assets/icons/vector_152_37.svg")
    )


def test_best_descendant_vector_asset_prefers_chevron_component() -> None:
    host = CleanDesignTreeNode(
        id="152:122",
        name="Icon/ Right",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="152:123",
                name="chevron-right",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
                vector_asset_key="assets/icons/chevron-right_152_123.svg",
                children=[
                    CleanDesignTreeNode(
                        id="152:124",
                        name="Vector",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=4.0, height=8.0),
                        style=NodeStyle(has_stroke=True),
                        vector_asset_key="assets/icons/vector_152_124.svg",
                    ),
                ],
            ),
        ],
    )
    assert _best_descendant_vector_asset(host) == "assets/icons/chevron-right_152_123.svg"


def test_trailing_chevron_stack_emits_centered_glyph_via_dispatch() -> None:
    emitted = render_node_body(_trailing_chevron_stack(), uses_svg=True)
    assert "vector_152_37.svg" in emitted
    assert "width: 4.0, height: 8.0" in emitted
    assert "Center(child:" in emitted
