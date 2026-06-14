"""Generator-level visual fidelity tests."""

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.layout import refine_text_stack_placement
from figma_flutter_agent.parser.stack_paint import (
    sort_absolute_stack_children as _sort_absolute_stack_children,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GradientFill,
    GradientStop,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_refine_text_stack_placement_stretches_centered_text() -> None:
    placement = StackPlacement(horizontal="LEFT", vertical="TOP", left=46.0, top=12.0)
    style = NodeStyle(text_align="CENTER")

    refined = refine_text_stack_placement(NodeType.TEXT, style, NodeType.STACK, placement)

    assert refined is not None
    assert refined.horizontal == "LEFT_RIGHT"
    assert refined.left == 0.0
    assert refined.right == 0.0
    assert refined.top == 12.0


def test_multiline_text_renders_escaped_dart_literal() -> None:
    body = CleanDesignTreeNode(
        id="2",
        name="Body",
        type=NodeType.TEXT,
        text="Everyday is best, but we recommend picking\nat least five.",
        style=NodeStyle(font_size=16.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20.0, top=552.0),
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[body],
    )

    layout = render_layout_file(screen, feature_name="reminders", uses_svg=False)[
        "lib/generated/reminders_layout.dart"
    ]

    assert "Text('Everyday is best, but we recommend picking\\nat least five.'" in layout


def test_centered_title_text_renders_left_right_positioned() -> None:
    title = CleanDesignTreeNode(
        id="2",
        name="Subtitle",
        type=NodeType.TEXT,
        text="7 DAYS OF CALM",
        style=NodeStyle(text_align="CENTER", font_size=14.0),
        stack_placement=StackPlacement(
            horizontal="LEFT_RIGHT",
            vertical="TOP",
            left=0.0,
            right=0.0,
            top=53.5,
        ),
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Title Group",
        type=NodeType.STACK,
        sizing=Sizing(width=264.0, height=66.0),
        children=[title],
    )

    layout = render_layout_file(parent, feature_name="title", uses_svg=False)[
        "lib/generated/title_layout.dart"
    ]

    assert "Positioned(left: 0.0, right: 0.0" in layout
    assert "textAlign: TextAlign.center" in layout


def test_icon_in_square_stack_uses_positioned_fill_and_center() -> None:
    icon = CleanDesignTreeNode(
        id="3",
        name="Close",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/close.svg",
        sizing=Sizing(width=17.0, height=17.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20.5, top=20.5),
    )
    button = CleanDesignTreeNode(
        id="2",
        name="Button",
        type=NodeType.STACK,
        sizing=Sizing(width=55.0, height=55.0),
        children=[
            CleanDesignTreeNode(
                id="4",
                name="Circle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=55.0, height=55.0),
                style=NodeStyle(background_color="0xFFFFFFFF", border_radius=27.5),
            ),
            icon,
        ],
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[button],
    )

    layout = render_layout_file(screen, feature_name="icon_btn", uses_svg=True)[
        "lib/generated/icon_btn_layout.dart"
    ]

    assert "Positioned.fill(child: Center(child: SvgPicture.asset(" in layout


def test_blurred_vector_prefers_native_blur_when_filter_without_png() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Glow",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/glow.svg",
        vector_svg_has_filter=True,
        sizing=Sizing(width=120.0, height=120.0),
        style=NodeStyle(background_color="0xFFFCFCFC"),
    )

    body = render_node_body(node, uses_svg=True)

    assert "SvgPicture.asset('assets/icons/glow.svg'" not in body
    assert "Image.asset" not in body
    assert "BoxShadow" not in body


def test_blurred_vector_prefers_baked_png_when_available() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Glow",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/glow.svg",
        image_asset_key="assets/images/glow.png",
        vector_svg_has_filter=True,
        sizing=Sizing(width=120.0, height=120.0),
        style=NodeStyle(background_color="0xFFFCFCFC", layer_blur=55.0),
    )

    body = render_node_body(node, uses_svg=True)

    assert "Image.asset('assets/images/glow.png'" in body
    assert "SvgPicture.asset" not in body
    assert "BoxShadow" not in body


def test_blurred_vector_without_asset_falls_back_to_native_container() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Glow",
        type=NodeType.VECTOR,
        sizing=Sizing(width=256.0, height=244.0),
        style=NodeStyle(background_color="0xFFFFFFFF", layer_blur=55.0),
    )

    body = render_node_body(node, uses_svg=True)

    assert "SvgPicture.asset" not in body
    assert "BorderRadius.all(Radius.elliptical" in body
    assert "ImageFiltered" in body
    assert "ImageFilter.blur" in body


def test_blurred_vector_without_asset_renders_native_circle_when_square() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Glow",
        type=NodeType.VECTOR,
        sizing=Sizing(width=120.0, height=120.0),
        style=NodeStyle(background_color="0xFFFCFCFC", layer_blur=55.0),
    )

    body = render_node_body(node, uses_svg=True)

    assert "SvgPicture.asset" not in body
    assert "ImageFiltered" in body
    assert "BoxShape.circle" in body


def test_skip_control_text_uses_figma_position_not_fill_center() -> None:
    skip_stack = CleanDesignTreeNode(
        id="1",
        name="Skip",
        type=NodeType.STACK,
        sizing=Sizing(width=38.77, height=39.04),
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Arrow",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_forward.svg",
                sizing=Sizing(width=38.77, height=39.04),
                style=NodeStyle(has_stroke=True),
                stack_placement=StackPlacement(
                    horizontal="SCALE",
                    vertical="SCALE",
                    left=0.0,
                    top=0.0,
                    width=38.77,
                    height=39.04,
                ),
            ),
            CleanDesignTreeNode(
                id="3",
                name="15",
                type=NodeType.TEXT,
                text="15",
                sizing=Sizing(width=15.91, height=13.0),
                style=NodeStyle(text_color="0xFFA0A3B1", font_size=12.0),
                stack_placement=StackPlacement(
                    horizontal="LEFT",
                    vertical="TOP",
                    left=11.43,
                    top=13.02,
                    width=15.91,
                    height=13.0,
                ),
            ),
        ],
    )

    body = render_node_body(skip_stack, uses_svg=True)

    assert "Positioned.fill" not in body
    assert "left: 11.4" in body
    assert "top: 15.5" in body
    assert "width: 15.9" in body
    assert "height: 13.0" in body
    assert "textAlign: TextAlign.center" in body
    assert "Center(child:" in body
    assert "BoxFit.contain" in body


def test_full_artboard_with_date_numerals_is_not_skip_control_stack() -> None:
    from figma_flutter_agent.generator.layout.widgets.svg import _is_skip_control_stack

    artboard = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[
            CleanDesignTreeNode(
                id="hero",
                name="Hero",
                type=NodeType.STACK,
                sizing=Sizing(width=451.0, height=839.0),
                vector_asset_key="assets/illustrations/hero.svg",
                stack_placement=StackPlacement(left=-38.0, top=-14.0, width=451.0, height=839.0),
            ),
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="Screen title",
                sizing=Sizing(width=131.0, height=24.0),
                style=NodeStyle(font_size=19.0, text_align="CENTER"),
                stack_placement=StackPlacement(left=122.0, top=28.0, width=131.0, height=24.0),
            ),
            *[
                CleanDesignTreeNode(
                    id=f"day-{index}",
                    name="Day",
                    type=NodeType.TEXT,
                    text=str(20 + index),
                    sizing=Sizing(width=22.0, height=24.0),
                    stack_placement=StackPlacement(
                        left=24.0 + index * 64.0,
                        top=120.0,
                        width=22.0,
                        height=24.0,
                    ),
                )
                for index in range(5)
            ],
            CleanDesignTreeNode(
                id="stroke",
                name="Stroke",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/stroke.svg",
                sizing=Sizing(width=66.0, height=34.0),
                style=NodeStyle(has_stroke=True),
                stack_placement=StackPlacement(left=0.0, top=0.0, width=66.0, height=34.0),
            ),
        ],
    )

    assert not _is_skip_control_stack(artboard)

    body = render_layout_file(artboard, feature_name="calendar_header", uses_svg=True)[
        "lib/generated/calendar_header_layout.dart"
    ]

    assert "top: 396.5" not in body
    assert "top: 28.0" in body
    assert "Slider(" not in body


def test_clock_labels_and_illustration_stack_do_not_emit_playback_slider() -> None:
    from figma_flutter_agent.generator.layout.widgets.playback import (
        _playback_seek_vector_ids,
    )

    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[
            CleanDesignTreeNode(
                id="hero",
                name="Hero",
                type=NodeType.STACK,
                sizing=Sizing(width=451.0, height=839.0),
                vector_asset_key="assets/illustrations/hero.svg",
            ),
            CleanDesignTreeNode(
                id="time-a",
                name="Time",
                type=NodeType.TEXT,
                text="10:00 AM",
                sizing=Sizing(width=60.0, height=16.0),
            ),
            CleanDesignTreeNode(
                id="time-b",
                name="Time",
                type=NodeType.TEXT,
                text="12:00 PM",
                sizing=Sizing(width=60.0, height=16.0),
            ),
            CleanDesignTreeNode(
                id="vec-a",
                name="Chip",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/chip_a.svg",
                sizing=Sizing(width=66.0, height=34.0),
            ),
            CleanDesignTreeNode(
                id="vec-b",
                name="Chip",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/chip_b.svg",
                sizing=Sizing(width=85.0, height=34.0),
            ),
        ],
    )

    assert _playback_seek_vector_ids(screen) == set()

    body = render_layout_file(screen, feature_name="task_cards", uses_svg=True)[
        "lib/generated/task_cards_layout.dart"
    ]
    assert "Slider(" not in body


def test_stroke_line_svg_uses_minimum_visible_height() -> None:
    track = CleanDesignTreeNode(
        id="1",
        name="Track",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/track.svg",
        sizing=Sizing(width=333.0, height=0.0),
        style=NodeStyle(has_stroke=True, border_width=3.0),
    )

    body = render_node_body(track, uses_svg=True)

    assert "height: 3.0" in body
    assert "BoxFit.fill" in body


def test_blurred_vector_without_asset_renders_native_container() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Glow",
        type=NodeType.VECTOR,
        sizing=Sizing(width=257.0, height=244.0),
        style=NodeStyle(background_color="0xFFFCFCFC", layer_blur=55.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=-88.0, top=201.0),
    )

    body = render_node_body(node, uses_svg=True)

    assert "SvgPicture.asset" not in body
    assert "ImageFiltered" in body
    assert "ImageFilter.blur" in body


def test_play_pause_core_uses_union_of_dark_quadrants() -> None:
    pause = CleanDesignTreeNode(
        id="2",
        name="Pause Control",
        type=NodeType.STACK,
        sizing=Sizing(width=109.0, height=109.0),
        children=[
            CleanDesignTreeNode(
                id="8",
                name="Dark Core",
                type=NodeType.STACK,
                sizing=Sizing(width=88.0, height=88.0),
                children=[
                    CleanDesignTreeNode(
                        id="3",
                        name="Q1",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=44.0, height=44.0),
                        style=NodeStyle(background_color="0xFF3F414E"),
                        stack_placement=StackPlacement(
                            horizontal="LEFT", vertical="TOP", left=44.0, top=0.0
                        ),
                    ),
                    CleanDesignTreeNode(
                        id="4",
                        name="Q2",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=44.0, height=44.0),
                        style=NodeStyle(background_color="0xFF3F414E"),
                        stack_placement=StackPlacement(
                            horizontal="LEFT", vertical="TOP", left=44.0, top=44.0
                        ),
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="5",
                name="Bar 1",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=6.5, height=24.0),
                style=NodeStyle(background_color="0xFFFBFBFB", border_radius=14.0),
            ),
            CleanDesignTreeNode(
                id="6",
                name="Bar 2",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=6.5, height=24.0),
                style=NodeStyle(background_color="0xFFFBFBFB", border_radius=14.0),
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[pause],
    )

    layout = render_layout_file(screen, feature_name="player", uses_svg=False)[
        "lib/generated/player_layout.dart"
    ]

    assert "width: 88.0, height: 88.0" in layout


def test_square_thumb_containers_merge_into_ring() -> None:
    outer = CleanDesignTreeNode(
        id="1",
        name="Outer",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=17.0, height=17.0),
        style=NodeStyle(background_color="0xFF3F414E"),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=44.0, top=159.0),
    )
    inner = CleanDesignTreeNode(
        id="2",
        name="Inner",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=13.0, height=13.0),
        style=NodeStyle(background_color="0xFF3F414E"),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=46.0, top=161.0),
    )
    slider = CleanDesignTreeNode(
        id="3",
        name="Slider",
        type=NodeType.STACK,
        children=[outer, inner],
    )

    layout = render_layout_file(slider, feature_name="slider", uses_svg=False)[
        "lib/generated/slider_layout.dart"
    ]

    assert "shape: BoxShape.circle" in layout
    assert layout.count("BoxShape.circle") >= 2


def test_gradient_ellipse_prefers_exported_svg() -> None:
    ellipse = CleanDesignTreeNode(
        id="1",
        name="Ellipse 47",
        type=NodeType.CONTAINER,
        vector_asset_key="assets/icons/ellipse_47.svg",
        rotation=1.238,
        sizing=Sizing(width=266.93, height=266.93),
        style=NodeStyle(
            gradient=GradientFill(
                type="linear",
                stops=[GradientStop(color="0xFFF3EDE4", position=0.0)],
            )
        ),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=234.16,
            top=666.13,
            width=266.93,
            height=266.93,
        ),
    )

    body = render_node_body(ellipse, uses_svg=True)

    assert "SvgPicture.asset('assets/icons/ellipse_47.svg'" in body
    assert "LinearGradient" not in body


def test_nested_absolute_stack_preserves_figma_child_order() -> None:
    """Smaller top-layer vector must stay above a larger sibling (not area-sorted)."""
    back = CleanDesignTreeNode(
        id="1:back",
        name="Back",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/back.svg",
        sizing=Sizing(width=200.0, height=200.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=0.0, top=0.0),
    )
    front = CleanDesignTreeNode(
        id="1:front",
        name="Front",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/front.svg",
        sizing=Sizing(width=20.0, height=20.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=10.0, top=10.0),
    )
    stack = CleanDesignTreeNode(
        id="1:stack",
        name="Art",
        type=NodeType.STACK,
        children=[back, front],
    )

    ordered = _sort_absolute_stack_children(stack.children, is_layout_root=False)
    assert [child.id for child in ordered] == ["1:back", "1:front"]

    body = render_node_body(stack, uses_svg=True, is_layout_root=False)
    back_index = body.index("back.svg")
    front_index = body.index("front.svg")
    assert back_index < front_index


def test_concentric_circle_pair_renders_thumb_ring() -> None:
    outer = CleanDesignTreeNode(
        id="3",
        name="Outer",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=17.0, height=17.0),
        style=NodeStyle(background_color="0xFF3F414E", border_radius=8.5),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=44.0, top=159.0),
    )
    inner = CleanDesignTreeNode(
        id="4",
        name="Inner",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=13.0, height=13.0),
        style=NodeStyle(background_color="0xFF3F414E", border_radius=6.5),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=46.0, top=161.0),
    )
    slider = CleanDesignTreeNode(
        id="2",
        name="Slider",
        type=NodeType.STACK,
        children=[outer, inner],
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[slider],
    )

    layout = render_layout_file(screen, feature_name="slider", uses_svg=False)[
        "lib/generated/slider_layout.dart"
    ]

    assert "withOpacity(0.24)" in layout
    assert layout.count("BoxShape.circle") >= 2
