"""Tap-target codegen for classic absolute stacks (back nav, skip, player chrome)."""

from __future__ import annotations

from figma_flutter_agent.generator.cluster_variants import collect_cluster_vector_variants
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.dedup.prune import prune_duplicated_cluster_subtrees
from figma_flutter_agent.parser.interaction import (
    looks_like_back_nav_stack,
    looks_like_compact_icon_action_stack,
    looks_like_media_controls_stack,
    looks_like_play_pause_control_stack,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def _deep_back_nav_stack() -> CleanDesignTreeNode:
    """Figma-style nested chrome: outer stack wraps circle + icon several levels deep."""
    icon = CleanDesignTreeNode(
        id="icon",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/close.svg",
        sizing=Sizing(width=14.0, height=14.0),
    )
    inner = CleanDesignTreeNode(
        id="inner",
        name="Inner",
        type=NodeType.STACK,
        sizing=Sizing(width=55.0, height=55.0),
        children=[
            CleanDesignTreeNode(
                id="circle",
                name="Circle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=55.0, height=55.0),
                style={"backgroundColor": "0xFFFFFFFF", "borderRadius": 27.5},
                children=[],
            ),
            CleanDesignTreeNode(
                id="icon-wrap",
                name="IconWrap",
                type=NodeType.STACK,
                sizing=Sizing(width=55.0, height=55.0),
                children=[icon],
            ),
        ],
    )
    return CleanDesignTreeNode(
        id="back",
        name="Back",
        type=NodeType.STACK,
        sizing=Sizing(width=55.0, height=55.0),
        stack_placement=StackPlacement(left=20.0, top=50.0, width=55.0, height=55.0),
        children=[inner],
    )


def test_looks_like_back_nav_detects_deep_nested_icon() -> None:
    assert looks_like_back_nav_stack(_deep_back_nav_stack())


def test_render_deep_back_nav_emits_ink_well() -> None:
    body = render_node_body(_deep_back_nav_stack(), uses_svg=True)
    assert "InkWell(" in body or "GestureDetector(" in body
    assert "custom-code:" in body and ("back-nav" in body or "button-action" in body)


def test_play_pause_uses_circular_ink_well() -> None:
    play = CleanDesignTreeNode(
        id="play",
        name="Play",
        type=NodeType.STACK,
        sizing=Sizing(width=109.0, height=109.0),
        render_boundary=True,
        flatten_figma_node_ids=[f"leaf-{i}" for i in range(8)],
        stack_placement=StackPlacement(left=0.0, top=0.0, width=109.0, height=109.0),
    )
    body = render_node_body(play, uses_svg=True)
    assert "customBorder: const CircleBorder()" in body
    assert "BoxShape.circle" in body


def test_collapsed_play_pause_boundary_renders_native_control() -> None:
    collapsed = CleanDesignTreeNode(
        id="play",
        name="Play",
        type=NodeType.STACK,
        sizing=Sizing(width=109.0, height=109.0),
        render_boundary=True,
        flatten_figma_node_ids=[f"n{i}" for i in range(8)],
        stack_placement=StackPlacement(left=88.8, width=109.0, height=109.0),
    )
    assert looks_like_play_pause_control_stack(collapsed)
    body = render_node_body(collapsed, uses_svg=True)
    assert "InkWell(" in body
    assert "BoxShape.circle" in body
    assert "group_6834" not in body


def test_media_controls_with_collapsed_play_emits_slider_and_ink_wells() -> None:
    play = CleanDesignTreeNode(
        id="play",
        name="Play",
        type=NodeType.STACK,
        sizing=Sizing(width=109.0, height=109.0),
        render_boundary=True,
        flatten_figma_node_ids=[f"leaf-{i}" for i in range(8)],
        stack_placement=StackPlacement(left=88.8, width=109.0, height=109.0),
    )
    forward = CleanDesignTreeNode(
        id="fwd",
        name="Skip forward",
        type=NodeType.STACK,
        cluster_id="cluster_skip",
        sizing=Sizing(width=39.0, height=39.0),
        stack_placement=StackPlacement(left=247.8, width=39.0, height=39.0),
        children=[
            CleanDesignTreeNode(
                id="fwd-vec",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_fwd.svg",
                sizing=Sizing(width=39.0, height=39.0),
            ),
            CleanDesignTreeNode(
                id="fwd-num",
                name="15",
                type=NodeType.TEXT,
                text="15",
                sizing=Sizing(width=16.0, height=13.0),
            ),
        ],
    )
    backward = CleanDesignTreeNode(
        id="back",
        name="Skip back",
        type=NodeType.STACK,
        cluster_id="cluster_skip",
        sizing=Sizing(width=39.0, height=39.0),
        stack_placement=StackPlacement(right=247.8, width=39.0, height=39.0),
        children=[
            CleanDesignTreeNode(
                id="back-vec",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_back.svg",
                sizing=Sizing(width=39.0, height=39.0),
            ),
        ],
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Transport row",
        type=NodeType.STACK,
        sizing=Sizing(width=286.6, height=109.0),
        children=[play, forward, backward],
    )
    track = CleanDesignTreeNode(
        id="track",
        name="Track",
        type=NodeType.VECTOR,
        sizing=Sizing(width=333.0, height=0.0),
        vector_asset_key="assets/icons/track.svg",
        stack_placement=StackPlacement(left=20.0, top=123.5, width=333.0, height=0.0),
    )
    thumb = CleanDesignTreeNode(
        id="thumb",
        name="Thumb",
        type=NodeType.VECTOR,
        sizing=Sizing(width=28.0, height=0.0),
        vector_asset_key="assets/icons/thumb.svg",
        stack_placement=StackPlacement(left=20.0, top=123.5, width=28.0, height=0.0),
    )
    controls = CleanDesignTreeNode(
        id="controls",
        name="Player controls",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=201.3),
        stack_placement=StackPlacement(left=20.0, top=484.5, width=374.0, height=201.3),
        children=[
            row,
            track,
            thumb,
            CleanDesignTreeNode(
                id="t0",
                name="01:30",
                type=NodeType.TEXT,
                text="01:30",
                sizing=Sizing(width=40.0, height=13.0),
                stack_placement=StackPlacement(left=20.0, top=144.0, width=40.0, height=13.0),
            ),
            CleanDesignTreeNode(
                id="t1",
                name="45:00",
                type=NodeType.TEXT,
                text="45:00",
                sizing=Sizing(width=40.0, height=13.0),
                stack_placement=StackPlacement(left=333.0, top=144.0, width=40.0, height=13.0),
            ),
        ],
    )
    prune_duplicated_cluster_subtrees(controls)
    assert looks_like_media_controls_stack(controls)
    variants = collect_cluster_vector_variants([controls], {})
    body = render_node_body(controls, uses_svg=True, cluster_vector_variants=variants)
    assert "Slider(" in body
    assert body.count("Slider(") == 1
    assert body.count("InkWell(") >= 3
    assert "vector_back.svg" in body
    assert "BoxShape.circle" in body
    assert "withOpacity(0.24)" not in body
    assert "CircleBorder()" in body


def test_pruned_skip_cluster_uses_circular_ink() -> None:
    skip = CleanDesignTreeNode(
        id="skip-back",
        name="Group 6836",
        type=NodeType.STACK,
        cluster_id="cluster_skip",
        sizing=Sizing(width=38.8, height=39.0),
        vector_asset_key="assets/icons/vector_1_4020.svg",
        stack_placement=StackPlacement(right=247.8, width=38.8, height=39.0),
        children=[],
    )
    body = render_node_body(skip, uses_svg=True)
    assert "customBorder: const CircleBorder()" in body
    assert "shape: const CircleBorder()" in body


def test_deep_nested_circular_chrome_uses_circular_ink() -> None:
    circle = CleanDesignTreeNode(
        id="circle",
        name="Circle",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=55.0, height=55.0),
        style={"backgroundColor": "0xFFFFFFFF", "borderRadius": 38.0},
    )
    inner = CleanDesignTreeNode(
        id="inner",
        name="Inner",
        type=NodeType.STACK,
        sizing=Sizing(width=55.0, height=55.0),
        children=[
            CleanDesignTreeNode(
                id="mid",
                name="Mid",
                type=NodeType.STACK,
                sizing=Sizing(width=55.0, height=55.0),
                children=[
                    CleanDesignTreeNode(
                        id="wrap",
                        name="Wrap",
                        type=NodeType.STACK,
                        sizing=Sizing(width=55.0, height=55.0),
                        children=[circle],
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="icon",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/close.svg",
                sizing=Sizing(width=14.0, height=14.0),
            ),
        ],
    )
    chrome = CleanDesignTreeNode(
        id="chrome",
        name="Close",
        type=NodeType.STACK,
        sizing=Sizing(width=55.0, height=55.0),
        stack_placement=StackPlacement(left=20.0, top=50.0, width=55.0, height=55.0),
        children=[inner],
    )
    body = render_node_body(chrome, uses_svg=True)
    assert "customBorder: const CircleBorder()" in body


def test_render_skip_control_with_children_emits_tap_target() -> None:
    skip = CleanDesignTreeNode(
        id="skip",
        name="Skip",
        type=NodeType.STACK,
        sizing=Sizing(width=39.0, height=39.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=39.0, height=39.0),
        children=[
            CleanDesignTreeNode(
                id="arc",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/skip.svg",
                sizing=Sizing(width=39.0, height=39.0),
            ),
            CleanDesignTreeNode(
                id="num",
                name="15",
                type=NodeType.TEXT,
                text="15",
                sizing=Sizing(width=16.0, height=13.0),
                stack_placement=StackPlacement(left=11.0, top=15.0, width=16.0, height=13.0),
            ),
        ],
    )
    body = render_node_body(skip, uses_svg=True)
    assert "InkWell(" in body or "GestureDetector(" in body


def _compact_arrow_back_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="42:3463",
        name="arrow-narrow-left",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        component_ref="3:4467",
        variant=ComponentVariant(
            component_id="3:4467",
            component_name="arrow-narrow-left",
        ),
        stack_placement=StackPlacement(left=24.0, top=24.0, width=24.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="vec",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/arrow.svg",
                sizing=Sizing(width=14.0, height=8.0),
            ),
        ],
    )


def test_compact_arrow_component_detected_as_back_nav() -> None:
    node = _compact_arrow_back_stack()
    assert looks_like_compact_icon_action_stack(node)
    assert looks_like_back_nav_stack(node)


def test_render_compact_arrow_emits_back_nav_tap_target() -> None:
    body = render_node_body(_compact_arrow_back_stack(), uses_svg=True)
    assert "InkWell(" in body or "GestureDetector(" in body
    assert "custom-code:" in body and ("back-nav" in body or "button-action" in body)


def test_button_stack_label_with_icon_centers_in_row() -> None:
    button = CleanDesignTreeNode(
        id="btn",
        name="Group 6793",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(left=20.0, top=200.0, width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=374.0, height=63.0),
                style={"backgroundColor": "0xFF7583CA", "borderRadius": 38.0},
            ),
            CleanDesignTreeNode(
                id="icon",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/facebook.svg",
                sizing=Sizing(width=24.0, height=24.0),
                stack_placement=StackPlacement(left=24.0, top=19.0, width=24.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="label",
                name="CONTINUE WITH FACEBOOK",
                type=NodeType.TEXT,
                text="CONTINUE WITH FACEBOOK",
                sizing=Sizing(width=200.0, height=14.0),
                style={"glyphTopOffset": 2.8, "glyphHeight": 10.5},
                stack_placement=StackPlacement(left=92.0, top=13.0, width=200.0, height=14.0),
            ),
        ],
    )
    body = render_node_body(button, uses_svg=False)
    assert "Alignment.center" in body
    assert "textAlign: TextAlign.center" in body
    assert "InkWell(" in body
    assert "top: 13.0" not in body or "height: 63.0" in body


def test_button_stack_label_without_icon_uses_vertical_align() -> None:
    button = CleanDesignTreeNode(
        id="btn",
        name="Log in",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(left=20.0, top=200.0, width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=374.0, height=63.0),
                style={"backgroundColor": "0xFF7583CA", "borderRadius": 38.0},
            ),
            CleanDesignTreeNode(
                id="label",
                name="LOG IN",
                type=NodeType.TEXT,
                text="LOG IN",
                sizing=Sizing(width=80.0, height=14.0),
                stack_placement=StackPlacement(left=147.0, top=24.0, width=80.0, height=14.0),
            ),
        ],
    )
    body = render_node_body(button, uses_svg=False)
    assert "Alignment.center" in body
    assert "height: 63.0" in body


def _social_auth_row(row_id: str, *, top: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=row_id,
        name="SocialRow",
        type=NodeType.ROW,
        children=[
            CleanDesignTreeNode(
                id=f"{row_id}:icon",
                name="Icon",
                type=NodeType.VECTOR,
                stack_placement=StackPlacement(
                    left=16.0,
                    top=16.0,
                    width=24.0,
                    height=24.0,
                ),
            ),
            CleanDesignTreeNode(
                id=f"{row_id}:label",
                name="Label",
                type=NodeType.TEXT,
                text="Continue",
                stack_placement=StackPlacement(
                    left=56.0,
                    top=20.0,
                    width=240.0,
                    height=16.0,
                ),
            ),
        ],
        stack_placement=StackPlacement(left=24.0, top=top, width=327.0, height=48.0),
    )


def _social_auth_button_flex(row_id: str) -> CleanDesignTreeNode:
    """Social auth button with flex ``sizing`` (icon + label as direct children)."""
    return CleanDesignTreeNode(
        id=row_id,
        name="Continue with Google",
        type=NodeType.BUTTON,
        sizing=Sizing(width=327.0, height=48.0),
        spacing=10.0,
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFEFF0F6",
            border_radius=10.0,
        ),
        children=[
            CleanDesignTreeNode(
                id=f"{row_id}:icon",
                name="Icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=18.0, height=18.0),
            ),
            CleanDesignTreeNode(
                id=f"{row_id}:label",
                name="Label",
                type=NodeType.TEXT,
                text="Continue with Google",
                sizing=Sizing(width=144.0, height=20.0),
            ),
        ],
    )


def _social_auth_row_flex(row_id: str) -> CleanDesignTreeNode:
    """Social auth row with flex ``sizing`` only (no ``stack_placement``)."""
    return CleanDesignTreeNode(
        id=row_id,
        name="SocialRow",
        type=NodeType.ROW,
        sizing=Sizing(width=327.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id=f"{row_id}:icon",
                name="Icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=24.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id=f"{row_id}:label",
                name="Label",
                type=NodeType.TEXT,
                text="Continue with Google",
                sizing=Sizing(width=240.0, height=16.0),
            ),
        ],
    )


def test_multiple_social_auth_rows_emit_separate_inkwells() -> None:
    host = CleanDesignTreeNode(
        id="host",
        name="SocialGroup",
        type=NodeType.BUTTON,
        spacing=15.0,
        sizing=Sizing(width=327.0, height=111.0),
        children=[
            _social_auth_row("google", top=0.0),
            _social_auth_row("facebook", top=63.0),
        ],
    )
    body = render_node_body(host, uses_svg=False)
    assert body.count("InkWell(") >= 2


def test_multiple_social_auth_rows_flex_sizing_emit_separate_inkwells() -> None:
    from figma_flutter_agent.parser.geometry import enrich_clean_tree_from_geometry

    host = CleanDesignTreeNode(
        id="host",
        name="Button",
        type=NodeType.BUTTON,
        spacing=15.0,
        sizing=Sizing(width=327.0, height=111.0),
        children=[
            _social_auth_row_flex("google"),
            _social_auth_row_flex("facebook"),
        ],
    )
    enrich_clean_tree_from_geometry(host)
    body = render_node_body(host, uses_svg=False)
    assert body.count("InkWell(") >= 2


def test_social_auth_group_emits_column_not_stack() -> None:
    from figma_flutter_agent.parser.geometry import enrich_clean_tree_from_geometry

    host = CleanDesignTreeNode(
        id="host",
        name="Button",
        type=NodeType.BUTTON,
        spacing=15.0,
        sizing=Sizing(width=327.0, height=111.0),
        children=[
            _social_auth_row_flex("google"),
            _social_auth_row_flex("facebook"),
        ],
    )
    enrich_clean_tree_from_geometry(host)
    assert all(child.type == NodeType.BUTTON for child in host.children)
    body = render_node_body(host, uses_svg=False)
    assert "Column(" in body
    assert "Stack(fit: StackFit.expand" not in body
    assert body.count("InkWell(") >= 2


def test_social_auth_row_emits_icon_label_row_not_expand_stack() -> None:
    from figma_flutter_agent.parser.geometry import enrich_clean_tree_from_geometry

    button = _social_auth_button_flex("google")
    enrich_clean_tree_from_geometry(button)
    body = render_node_body(button, uses_svg=False)
    assert "Row(" in body
    assert "mainAxisAlignment: MainAxisAlignment.center" in body
    assert "crossAxisAlignment: CrossAxisAlignment.center" in body
    assert "Expanded(child: Align(alignment: Alignment.center" not in body
    assert "Stack(fit: StackFit.expand" not in body


def test_button_icon_label_grouped_centered() -> None:
    from figma_flutter_agent.parser.geometry import enrich_clean_tree_from_geometry

    button = _social_auth_button_flex("google")
    enrich_clean_tree_from_geometry(button)
    body = render_node_body(button, uses_svg=False)
    icon_idx = body.find("SizedBox(width: 18.0, height: 18.0")
    label_idx = body.find("Continue with Google")
    assert icon_idx >= 0
    assert label_idx >= 0
    assert label_idx - icon_idx < 200
    assert "Expanded(child: Align(alignment: Alignment.center" not in body


def test_button_ink_surface_emits_brand_gradient() -> None:
    from figma_flutter_agent.generator.layout.widgets.button.core import (
        _button_ink_surface_params,
    )
    from figma_flutter_agent.schemas import GradientFill, GradientStop, NodeStyle

    surface = CleanDesignTreeNode(
        id="cta",
        name="CTA",
        type=NodeType.CONTAINER,
        style=NodeStyle(
            background_color="0xFF1D61E7",
            border_radius=10.0,
            gradient=GradientFill(
                type="linear",
                angle=90.0,
                stops=[
                    GradientStop(position=0.0, color="#FF1D61E7"),
                    GradientStop(position=1.0, color="#FF4D81E7"),
                ],
            ),
        ),
    )
    fill, _border, _shadows, gradient = _button_ink_surface_params(surface)
    assert fill is None
    assert gradient is not None
    assert "LinearGradient" in gradient
