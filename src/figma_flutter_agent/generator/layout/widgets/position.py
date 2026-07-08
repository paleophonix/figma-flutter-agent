"""Positioned bounds resolution, viewport wrappers, and stack-position helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.text_metrics import (
    center_pinned_text_explicit_lane_width,
    placement_is_center_pinned_horizontal,
    positioned_text_allows_metric_slack,
    positioned_text_preserves_right_edge,
    positioned_text_width_with_metric_slack,
)
from figma_flutter_agent.generator.layout.cupertino import wrap_scroll_viewport
from figma_flutter_agent.generator.layout.navigation.constants import (
    TOP_NAV_BACK_AFFORDANCE_MAX_LEFT,
    TOP_NAV_TRAILING_AFFORDANCE_MIN_CENTER_RATIO,
)
from figma_flutter_agent.generator.layout.style import (
    box_decoration_expr,
    has_box_decoration,
)
from figma_flutter_agent.parser.interaction.buttons import (
    _child_is_nav_icon_affordance,
    button_hosts_top_navigation_bar,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GeomRect,
    NodeType,
    StackPlacement,
)

from .decoration import _wrap_frosted_layer_blur
from .layout import (
    _resolved_bottom_offset,
    _should_pin_bottom,
    _stack_has_bottom_anchored_child,
)
from .shared import (
    _node_layout_size,
    figma_positioned_dimensions,
)


def top_navigation_bar_child_vertical_fields(
    parent_node: CleanDesignTreeNode | None,
    *,
    child_height: float,
) -> list[str] | None:
    """Return shared vertical center-lane pins for top navigation bar chrome."""
    from figma_flutter_agent.parser.interaction import button_hosts_top_navigation_bar

    if parent_node is None or not button_hosts_top_navigation_bar(parent_node):
        return None
    bar_height = parent_node.sizing.height
    if bar_height is None or bar_height <= 0 or child_height <= 0:
        return None
    top = (float(bar_height) - float(child_height)) / 2.0
    return [
        f"top: {format_geometry_literal(top)}",
        f"height: {format_geometry_literal(child_height)}",
    ]


def top_navigation_bar_title_should_screen_center(
    title: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Return True when a nav title should stretch and center between chrome affordances."""
    if title.type != NodeType.TEXT or parent_node is None:
        return False
    if parent_node.type != NodeType.BUTTON or not button_hosts_top_navigation_bar(parent_node):
        return False
    placement = title.stack_placement
    if placement is None:
        return False
    return placement_is_center_pinned_horizontal(placement)


def top_navigation_bar_title_lane_placement(
    title: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode,
) -> StackPlacement | None:
    """Return placement pins for a screen-centered nav title lane between affordances."""
    if title.type != NodeType.TEXT or parent_node.type != NodeType.BUTTON:
        return None
    if not top_navigation_bar_title_should_screen_center(title, parent_node):
        return None
    placement = title.stack_placement
    if placement is None:
        return None
    if placement_is_center_pinned_horizontal(placement):
        return placement
    bar_width = float(parent_node.sizing.width or 0.0)
    if bar_width <= 0.0:
        return None
    leading_edge = 0.0
    trailing_edge = bar_width
    for child in parent_node.children:
        if child.type == NodeType.TEXT:
            continue
        child_placement = child.stack_placement
        if child_placement is None or child_placement.left is None:
            continue
        if not _child_is_nav_icon_affordance(child):
            continue
        left = float(child_placement.left)
        child_width = float(child_placement.width or child.sizing.width or 0.0)
        right_edge = left + child_width
        center_x = left + child_width / 2.0
        if left <= TOP_NAV_BACK_AFFORDANCE_MAX_LEFT:
            leading_edge = max(leading_edge, right_edge)
        elif center_x >= bar_width * TOP_NAV_TRAILING_AFFORDANCE_MIN_CENTER_RATIO:
            trailing_edge = min(trailing_edge, left)
    if trailing_edge <= leading_edge:
        return None
    child_height = float(placement.height or title.sizing.height or 0.0)
    nav_vertical = top_navigation_bar_child_vertical_fields(
        parent_node,
        child_height=child_height,
    )
    update: dict[str, object] = {
        "horizontal": "LEFT_RIGHT",
        "left": leading_edge,
        "right": bar_width - trailing_edge,
    }
    if nav_vertical is not None and child_height > 0:
        bar_height = float(parent_node.sizing.height or 0.0)
        update["top"] = (bar_height - child_height) / 2.0
        update["height"] = child_height
    return placement.model_copy(update=update)


def _node_has_nested_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when the clean-tree subtree rooted at ``node`` contains a ``STACK`` node."""
    if node.type == NodeType.STACK:
        return True
    return any(_node_has_nested_stack(child) for child in node.children)


def _layout_rect_edge_origin(node: CleanDesignTreeNode) -> tuple[float | None, float | None]:
    """Return layout-rect top-left edges when geometry conservation provides them."""
    frame = node.geometry_frame
    if frame is None or frame.layout_rect is None:
        return None, None
    layout_rect: GeomRect = frame.layout_rect
    left = float(layout_rect.x) if layout_rect.x is not None else None
    top = float(layout_rect.y) if layout_rect.y is not None else None
    return left, top


def _synthesize_stack_placement_from_geometry(
    node: CleanDesignTreeNode,
) -> StackPlacement | None:
    """Build a ``StackPlacement`` from conserved geometry when Figma omitted pins."""
    left, top = _layout_rect_edge_origin(node)
    if left is None or top is None:
        return None
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        frame = node.geometry_frame
        if frame is not None and frame.layout_rect is not None:
            width = frame.layout_rect.width
            height = frame.layout_rect.height
    if width is None or height is None:
        return None
    return StackPlacement(
        left=left,
        top=top,
        width=float(width),
        height=float(height),
    )


def placement_dual_horizontal_insets_overconstrain(
    placement: StackPlacement,
    parent_width: float | None,
) -> bool:
    """Return True when ``left`` + ``right`` (+ width) cannot fit the parent stack."""
    if placement.left is None or placement.right is None:
        return False
    left = float(placement.left)
    right = float(placement.right)
    width = float(placement.width or 0.0)
    if parent_width is not None and parent_width > 0:
        parent = float(parent_width)
        if width > 0:
            return left + right + width > parent + 1.0
        return left + right >= parent - 1.0
    return False


def positioned_text_dual_pin_span(
    placement: StackPlacement,
    *,
    parent_width: float | None,
) -> float | None:
    """Return the horizontal span implied by dual ``left``/``right`` pins."""
    if placement.left is None or placement.right is None:
        return None
    if parent_width is None or parent_width <= 0:
        return None
    return float(parent_width) - float(placement.left) - float(placement.right)


def positioned_text_prefers_explicit_width_pins(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
    *,
    parent_width: float | None,
    width: float | None,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """Prefer ``width`` pins over dual horizontal stretch for bounded table cells."""
    if node.type != NodeType.TEXT:
        return False
    if width is None or width <= 0:
        return False
    if placement.left is None or placement.right is None:
        return False
    if top_navigation_bar_title_should_screen_center(node, parent_node):
        return False
    span = positioned_text_dual_pin_span(placement, parent_width=parent_width)
    if span is None:
        return False
    return span > float(width) + 2.0


def positioned_text_explicit_width_horizontal_fields(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
    *,
    width: float,
    left: float,
) -> list[str]:
    """Emit one horizontal pin plus explicit width for bounded text cells."""
    width_token = format_geometry_literal(width)
    text_align = (node.style.text_align or "").upper()
    layout_left, _ = _layout_rect_edge_origin(node)
    if text_align == "RIGHT" and placement.right is not None:
        return [
            f"right: {format_geometry_literal(placement.right)}",
            f"width: {width_token}",
        ]
    left_pin = layout_left if layout_left is not None else left
    return [
        f"left: {format_geometry_literal(left_pin)}",
        f"width: {width_token}",
    ]


def _placement_origin_edges(
    node: CleanDesignTreeNode,
) -> tuple[float | None, float | None]:
    """Return stack placement origin edges when geometry conservation provides them."""
    frame = node.geometry_frame
    if frame is None or frame.placement_origin is None:
        return None, None
    origin = frame.placement_origin
    left = float(origin.x) if origin.x is not None else None
    top = float(origin.y) if origin.y is not None else None
    return left, top


def _resolved_positioned_left_top(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
    *,
    parent_width: float | None = None,
) -> tuple[float | None, float | None]:
    """Prefer conserved layout-rect edges over corrupt anchor-style stack placements."""
    left = placement.left if placement.left is not None else node.offset_x
    top = placement.top if placement.top is not None else node.offset_y
    layout_left, layout_top = _layout_rect_edge_origin(node)
    origin_left, origin_top = _placement_origin_edges(node)
    placement_matches_origin = (
        top is not None and origin_top is not None and abs(float(top) - origin_top) < 1.5
    ) or (left is not None and origin_left is not None and abs(float(left) - origin_left) < 1.5)
    if layout_left is not None and (
        placement_dual_horizontal_insets_overconstrain(placement, parent_width)
        or (
            (placement.horizontal or "").upper() == "CENTER"
            and placement.left is not None
            and abs(float(placement.left) - layout_left) > 8.0
            and not (origin_left is not None and abs(float(placement.left) - origin_left) < 1.5)
        )
    ):
        left = layout_left
    if (
        layout_top is not None
        and top is not None
        and abs(float(top) - layout_top) > 8.0
        and not placement_matches_origin
        and (placement.vertical or "").upper() in {"CENTER", "TOP"}
    ):
        top = layout_top
    return left, top


def _positioned_horizontal_box_fields(
    placement: StackPlacement,
    *,
    width: float,
    left: float,
) -> list[str]:
    """Emit horizontal ``Positioned`` pins for a bounded stack child."""
    width_token = format_geometry_literal(width)
    horizontal = placement.horizontal
    if horizontal == "RIGHT":
        return [
            f"right: {format_geometry_literal(placement.right)}",
            f"width: {width_token}",
        ]
    if horizontal == "LEFT_RIGHT":
        return [
            f"left: {format_geometry_literal(left)}",
            f"right: {format_geometry_literal(placement.right)}",
        ]
    return [
        f"left: {format_geometry_literal(left)}",
        f"width: {width_token}",
    ]


def _ensure_positioned_stack_bounds(
    fields: list[str],
    node: CleanDesignTreeNode,
    placement: StackPlacement,
    *,
    parent_width: float | None = None,
    parent_height: float | None = None,
    prefer_top_pin: bool = False,
    parent_node: CleanDesignTreeNode | None = None,
) -> None:
    """Add explicit ``Positioned`` width/height pins from Figma frame size."""
    from figma_flutter_agent.generator.geometry.affine import (
        has_non_trivial_linear,
        is_axis_aligned,
        linear_affine,
    )

    frame = node.geometry_frame
    if frame is not None and (
        has_non_trivial_linear(linear_affine(frame.local_transform))
        or not is_axis_aligned(frame.local_transform)
    ):
        local = frame.local_transform
        intrinsic = frame.intrinsic_size
        fields[:] = [
            f"left: {format_geometry_literal(local.tx)}",
            f"top: {format_geometry_literal(local.ty)}",
            f"width: {format_geometry_literal(intrinsic.width)}",
            f"height: {format_geometry_literal(intrinsic.height)}",
        ]
        return
    if node.layout_slot is not None and node.layout_slot.residual_matrix is not None:
        residual = node.layout_slot.residual_matrix
        if has_non_trivial_linear(residual) or not is_axis_aligned(residual):
            intrinsic = frame.intrinsic_size if frame is not None else None
            if intrinsic is not None:
                fields[:] = [
                    f"left: {format_geometry_literal(residual.tx)}",
                    f"top: {format_geometry_literal(residual.ty)}",
                    f"width: {format_geometry_literal(intrinsic.width)}",
                    f"height: {format_geometry_literal(intrinsic.height)}",
                ]
                return
    from figma_flutter_agent.generator.layout.responsive import (
        should_stretch_artboard_positioned_horizontal,
        stretch_positioned_fields_horizontal,
    )

    width, height = figma_positioned_dimensions(node, placement)
    figma_width_before_slack: float | None = None
    lane_override = center_pinned_text_explicit_lane_width(
        node,
        placement,
        parent_width=parent_width,
    )
    if lane_override is not None and parent_width is not None:
        width = lane_override
        left_override = (float(parent_width) - lane_override) / 2.0
    else:
        left_override = None
    if positioned_text_allows_metric_slack(node, placement) and width is not None and width > 0:
        figma_width_before_slack = float(width)
        width = positioned_text_width_with_metric_slack(float(width))
    left, top = _resolved_positioned_left_top(
        node,
        placement,
        parent_width=parent_width,
    )
    if left_override is not None:
        left = left_override
    if (
        figma_width_before_slack is not None
        and width is not None
        and left is not None
        and parent_width is not None
        and positioned_text_preserves_right_edge(
            node,
            placement,
            parent_width=parent_width,
            figma_width=figma_width_before_slack,
        )
    ):
        left = float(parent_width) - float(width)
    pin_bottom = _should_pin_bottom(
        placement,
        parent_height=parent_height,
        prefer_top_pin=prefer_top_pin,
    ) or any(field.startswith("bottom:") for field in fields)
    if left is not None and top is not None and width is not None and height is not None:
        if should_stretch_artboard_positioned_horizontal(placement, width):
            height_token = format_geometry_literal(height)
            fields[:] = [
                f"left: {format_geometry_literal(left)}",
                f"top: {format_geometry_literal(top)}",
                f"height: {height_token}",
            ]
            stretch_positioned_fields_horizontal(fields)
            return
        width_token = format_geometry_literal(width)
        height_token = format_geometry_literal(height)
        horizontal = placement.horizontal
        prefer_fixed_width = positioned_text_prefers_explicit_width_pins(
            node,
            placement,
            parent_width=parent_width,
            width=width,
            parent_node=parent_node,
        ) or lane_override is not None
        if pin_bottom:
            bottom = _resolved_bottom_offset(placement, parent_height=parent_height)
            bottom_token = format_geometry_literal(bottom)
            if horizontal == "RIGHT":
                fields[:] = [
                    f"right: {format_geometry_literal(placement.right)}",
                    f"bottom: {bottom_token}",
                    f"width: {width_token}",
                    f"height: {height_token}",
                ]
            elif (
                placement.right is not None
                and (
                    horizontal == "LEFT_RIGHT"
                    or (
                        placement_is_center_pinned_horizontal(placement)
                        and not placement_dual_horizontal_insets_overconstrain(
                            placement,
                            parent_width,
                        )
                    )
                )
                and not prefer_fixed_width
            ):
                fields[:] = [
                    f"left: {format_geometry_literal(left)}",
                    f"right: {format_geometry_literal(placement.right)}",
                    f"bottom: {bottom_token}",
                    f"height: {height_token}",
                ]
            elif prefer_fixed_width:
                fields[:] = [
                    *positioned_text_explicit_width_horizontal_fields(
                        node,
                        placement,
                        width=float(width),
                        left=float(left),
                    ),
                    f"bottom: {bottom_token}",
                    f"height: {height_token}",
                ]
            else:
                fields[:] = [
                    f"left: {format_geometry_literal(left)}",
                    f"bottom: {bottom_token}",
                    f"width: {width_token}",
                    f"height: {height_token}",
                ]
        elif horizontal == "RIGHT":
            fields[:] = [
                f"right: {format_geometry_literal(placement.right)}",
                f"width: {width_token}",
                f"top: {format_geometry_literal(top)}",
                f"height: {height_token}",
            ]
        elif horizontal == "LEFT_RIGHT" or (
            placement_is_center_pinned_horizontal(placement)
            and not placement_dual_horizontal_insets_overconstrain(placement, parent_width)
        ):
            if prefer_fixed_width:
                fields[:] = [
                    *positioned_text_explicit_width_horizontal_fields(
                        node,
                        placement,
                        width=float(width),
                        left=float(left),
                    ),
                    f"top: {format_geometry_literal(top)}",
                    f"height: {height_token}",
                ]
            else:
                fields[:] = [
                    f"left: {format_geometry_literal(left)}",
                    f"right: {format_geometry_literal(placement.right)}",
                    f"top: {format_geometry_literal(top)}",
                    f"height: {height_token}",
                ]
        else:
            fields[:] = [
                f"left: {format_geometry_literal(left)}",
                f"top: {format_geometry_literal(top)}",
                f"width: {width_token}",
                f"height: {height_token}",
            ]
        return

    field_text = ", ".join(fields)
    has_horizontal_stretch = "left:" in field_text and "right:" in field_text
    has_vertical_stretch = "top:" in field_text and "bottom:" in field_text
    if (
        "width:" not in field_text
        and width is not None
        and width > 0
        and not has_horizontal_stretch
    ):
        if should_stretch_artboard_positioned_horizontal(placement, width):
            stretch_positioned_fields_horizontal(fields)
        else:
            fields.append(f"width: {format_geometry_literal(width)}")
    if (
        "height:" not in field_text
        and height is not None
        and height > 0
        and not has_vertical_stretch
    ):
        fields.append(f"height: {format_geometry_literal(height)}")


def _render_leaf_surface(node: CleanDesignTreeNode) -> str | None:
    """Render a leaf ``CONTAINER`` (e.g. Figma RECTANGLE) with fills/effects."""
    from figma_flutter_agent.generator.layout.style.decoration import (
        box_foreground_decoration_expr,
    )

    if node.type != NodeType.CONTAINER or not has_box_decoration(node.style):
        return None
    decoration = box_decoration_expr(
        node.style,
        width=node.sizing.width,
        height=node.sizing.height,
    )
    foreground = box_foreground_decoration_expr(
        node.style,
        width=node.sizing.width,
        height=node.sizing.height,
    )
    if decoration is None and foreground is None:
        return None
    from figma_flutter_agent.generator.layout.responsive import responsive_emit_width

    width = responsive_emit_width(node.sizing.width)
    height = node.sizing.height
    deco_field = f"decoration: {decoration}, " if decoration is not None else ""
    foreground_field = f"foregroundDecoration: {foreground}, " if foreground is not None else ""
    if width is not None and width > 0 and height is not None and height > 0:
        leaf = f"Container(width: {width}, height: {height}, {deco_field}{foreground_field})"
    elif width is not None and width > 0:
        leaf = f"Container(width: {width}, {deco_field}{foreground_field})"
    elif height is not None and height > 0:
        leaf = f"Container(height: {height}, {deco_field}{foreground_field})"
    else:
        leaf = f"Container({deco_field}{foreground_field})"
    leaf = leaf.replace(", )", ")")
    if node.style.layer_blur is not None and node.style.layer_blur > 0:
        return _wrap_frosted_layer_blur(node, leaf)
    return leaf


def _child_needs_positioned_bounds(node: CleanDesignTreeNode, widget: str) -> bool:
    """Return True when Figma provides explicit frame size for a ``Positioned`` child."""
    width, height = figma_positioned_dimensions(node)
    if width is not None or height is not None:
        return True
    if "Stack(" in widget:
        return True
    stripped = widget.strip()
    return stripped.startswith("Stack(") or stripped.startswith("Container(")


def _wrap_root_stack_viewport(
    node: CleanDesignTreeNode,
    stack_widget: str,
    *,
    is_layout_root: bool,
    responsive_enabled: bool = False,
    theme_variant: str = "material_3",
    viewport_pinned_layers: list[str] | None = None,
    preview_stack_widget: str | None = None,
) -> str:
    """Bound classic absolute frames to the Figma artboard (scroll or scale-down)."""
    if not is_layout_root:
        return stack_widget
    width, height = _node_layout_size(node, None)
    if width is None or height is None or width <= 0 or height <= 0:
        return stack_widget
    width_token = format_geometry_literal(width)
    height_token = format_geometry_literal(height)
    from figma_flutter_agent.generator.artboard import is_mobile_artboard_width
    from figma_flutter_agent.generator.layout.common import (
        artboard_preview_sized_box,
        wrap_artboard_preview_layout_builder,
    )

    if _stack_has_bottom_anchored_child(node):
        viewport_align = (
            "Alignment.topLeft" if is_mobile_artboard_width(width) else "Alignment.topCenter"
        )
        from figma_flutter_agent.generator.layout.common import (
            bottom_chrome_pinned_live_viewport,
            bottom_chrome_viewport_partition_live,
        )

        if responsive_enabled and is_mobile_artboard_width(width):
            if viewport_pinned_layers:
                fallback = bottom_chrome_viewport_partition_live(
                    scrollable_stack=stack_widget,
                    pinned_layers=viewport_pinned_layers,
                    width_token=width_token,
                    height_token=height_token,
                )
            else:
                fallback = (
                    "LayoutBuilder("
                    "builder: (context, constraints) {"
                    f"final viewportHeight = constraints.maxHeight.isFinite && "
                    f"constraints.maxHeight > 0 ? constraints.maxHeight : {height_token};"
                    "return SizedBox("
                    "width: constraints.maxWidth, "
                    f"height: viewportHeight, "
                    f"child: {stack_widget}"
                    ");"
                    "},"
                    ")"
                )
        elif responsive_enabled:
            fitted = (
                "Align("
                f"alignment: {viewport_align}, "
                "child: FittedBox("
                "fit: BoxFit.scaleDown, "
                f"alignment: {viewport_align}, "
                f"child: SizedBox(width: {width_token}, height: viewportHeight, "
                f"child: {stack_widget}),"
                "),"
                ")"
            )
            fallback = (
                "LayoutBuilder("
                "builder: (context, constraints) {"
                f"final viewportHeight = constraints.maxHeight.isFinite && "
                f"constraints.maxHeight > 0 ? constraints.maxHeight : {height_token};"
                f"return {fitted};"
                "},"
                ")"
            )
        else:
            from figma_flutter_agent.generator.layout.common import (
                bottom_chrome_pinned_live_viewport,
                bottom_chrome_viewport_partition_live,
            )

            if viewport_pinned_layers:
                fallback = bottom_chrome_viewport_partition_live(
                    scrollable_stack=stack_widget,
                    pinned_layers=viewport_pinned_layers,
                    width_token=width_token,
                    height_token=height_token,
                )
            else:
                fallback = bottom_chrome_pinned_live_viewport(
                    stack_widget=stack_widget,
                    width_token=width_token,
                    height_token=height_token,
                )
            fallback = wrap_scroll_viewport(
                fallback,
                theme_variant=theme_variant,
                anchor_top=True,
            )
        partitioned_preview = None
        if viewport_pinned_layers:
            partitioned_preview = bottom_chrome_viewport_partition_live(
                scrollable_stack=stack_widget,
                pinned_layers=viewport_pinned_layers,
                width_token="_artboardPreviewWidth",
                height_token="_artboardPreviewHeight",
            )
        preview_child = artboard_preview_sized_box(
            child=partitioned_preview or preview_stack_widget or stack_widget,
            alignment="Alignment.topLeft",
            bounded_child=True,
        )
        return wrap_artboard_preview_layout_builder(
            preview_child=preview_child,
            fallback=fallback,
            scroll_child=partitioned_preview,
            viewport_pin_bottom_chrome=bool(viewport_pinned_layers),
        )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        _stack_is_phone_shell_layout,
        stack_child_is_growable_panel,
        stack_child_is_positioned_only_stack,
    )

    growable_panels = sum(1 for child in node.children if stack_child_is_growable_panel(child))
    if node.type == NodeType.STACK and _stack_is_phone_shell_layout(
        node,
        growable_panels=growable_panels,
    ):
        # PhoneShellStaticViewportLaw: native chrome shells use a bounded Column with
        # Expanded body slots. An outer SingleChildScrollView gives unbounded flex
        # height and breaks capture/runtime layout; artboard preview stays bounded.
        preview_child = artboard_preview_sized_box(
            child=stack_widget,
            alignment="Alignment.topLeft",
            bounded_child=True,
        )
        if responsive_enabled:
            from figma_flutter_agent.generator.layout.common import (
                live_scroll_stack_viewport,
            )

            fallback = live_scroll_stack_viewport(
                stack_widget=stack_widget,
                artboard_height_token=height_token,
                pin_artboard_height=stack_child_is_positioned_only_stack(node),
            )
        else:
            shell_alignment = (
                "Alignment.topLeft" if is_mobile_artboard_width(width) else "Alignment.topCenter"
            )
            from figma_flutter_agent.generator.layout.common import static_artboard_viewport

            fallback = static_artboard_viewport(
                child=stack_widget,
                width_token=width_token,
                height_token=height_token,
                alignment=shell_alignment,
            )
        return wrap_artboard_preview_layout_builder(
            preview_child=preview_child,
            fallback=fallback,
        )
    from figma_flutter_agent.generator.artboard import is_tall_mobile_artboard
    from figma_flutter_agent.generator.layout.common import (
        live_scroll_stack_viewport,
        scroll_viewport_child_shell,
    )

    stack_alignment = (
        "Alignment.topLeft" if is_mobile_artboard_width(width) else "Alignment.topCenter"
    )
    pin_artboard_height = stack_child_is_positioned_only_stack(node)
    artboard = scroll_viewport_child_shell(
        width_expr=width_token,
        height_token=height_token,
        child=stack_widget,
        alignment=stack_alignment,
        tolerate_metric_drift=is_tall_mobile_artboard(width, height),
        pin_artboard_height=pin_artboard_height,
    )
    if responsive_enabled:
        fallback = live_scroll_stack_viewport(
            stack_widget=stack_widget,
            artboard_height_token=height_token,
            pin_artboard_height=pin_artboard_height,
        )
        preview_child = artboard_preview_sized_box(
            child=stack_widget,
            alignment=(
                "Alignment.topLeft" if is_mobile_artboard_width(width) else "Alignment.topCenter"
            ),
            bounded_child=True,
        )
        return wrap_artboard_preview_layout_builder(
            preview_child=preview_child,
            fallback=fallback,
        )
    if not responsive_enabled and not is_tall_mobile_artboard(width, height):
        shell_alignment = (
            "Alignment.topLeft" if is_mobile_artboard_width(width) else "Alignment.topCenter"
        )
        from figma_flutter_agent.generator.layout.common import static_artboard_viewport

        fallback = static_artboard_viewport(
            child=stack_widget,
            width_token=width_token,
            height_token=height_token,
            alignment=shell_alignment,
        )
        preview_child = artboard_preview_sized_box(
            child=stack_widget,
            alignment=stack_alignment,
            bounded_child=True,
        )
        return wrap_artboard_preview_layout_builder(
            preview_child=preview_child,
            fallback=fallback,
        )
    viewport = f"SingleChildScrollView(child: {artboard})"
    return wrap_scroll_viewport(viewport, theme_variant=theme_variant, anchor_top=True)


def _wrap_root_column_viewport(
    node: CleanDesignTreeNode,
    column_widget: str,
    *,
    responsive_enabled: bool,
    theme_variant: str,
) -> str:
    """Scroll tall phone column artboards in live viewports; keep full frame for goldens."""
    from figma_flutter_agent.generator.artboard import (
        is_mobile_artboard_width,
        is_tall_mobile_artboard,
    )
    from figma_flutter_agent.generator.layout.common import (
        artboard_preview_sized_box,
        live_scroll_column_viewport,
        scroll_viewport_child_shell,
        wrap_artboard_preview_layout_builder,
    )
    from figma_flutter_agent.generator.layout.cupertino import wrap_scroll_viewport

    width, height = _node_layout_size(node, None)
    if not is_tall_mobile_artboard(width, height):
        if (
            not responsive_enabled
            and width is not None
            and height is not None
            and width > 0
            and height > 0
        ):
            width_token = format_geometry_literal(width)
            height_token = format_geometry_literal(height)
            column_alignment = (
                "Alignment.topLeft" if is_mobile_artboard_width(width) else "Alignment.topCenter"
            )
            from figma_flutter_agent.generator.layout.common import static_artboard_viewport

            fallback = static_artboard_viewport(
                child=column_widget,
                width_token=width_token,
                height_token=height_token,
                alignment=column_alignment,
            )
            preview_child = artboard_preview_sized_box(child=column_widget)
            return wrap_artboard_preview_layout_builder(
                preview_child=preview_child,
                fallback=fallback,
            )
        return column_widget
    width_token = format_geometry_literal(width)
    height_token = format_geometry_literal(height)
    from figma_flutter_agent.generator.layout.stack_chrome import (
        column_hoists_docked_bottom_nav_stack,
    )

    if column_hoists_docked_bottom_nav_stack(node):
        viewport_column = (
            "Column("
            "mainAxisSize: MainAxisSize.max, "
            "crossAxisAlignment: CrossAxisAlignment.stretch, "
            f"children: [{column_widget}]"
            ")"
        )
        if responsive_enabled and is_mobile_artboard_width(width):
            fallback = (
                "LayoutBuilder("
                "builder: (context, constraints) {"
                f"final viewportHeight = constraints.maxHeight.isFinite && "
                f"constraints.maxHeight > 0 ? constraints.maxHeight : {height_token};"
                "return SizedBox("
                "width: constraints.maxWidth, "
                f"height: viewportHeight, "
                f"child: {viewport_column}"
                ");"
                "},"
                ")"
            )
        else:
            fallback = (
                "LayoutBuilder("
                "builder: (context, constraints) {"
                f"final viewportHeight = constraints.maxHeight.isFinite && "
                f"constraints.maxHeight > 0 ? constraints.maxHeight : {height_token};"
                "return SizedBox("
                f"width: {width_token}, "
                f"height: viewportHeight, "
                f"child: {viewport_column}"
                ");"
                "},"
                ")"
            )
        preview_child = artboard_preview_sized_box(child=viewport_column)
        return wrap_artboard_preview_layout_builder(
            preview_child=preview_child,
            fallback=fallback,
        )
    if responsive_enabled and is_mobile_artboard_width(width):
        fallback = live_scroll_column_viewport(
            artboard_width_expr="constraints.maxWidth",
            column_widget=column_widget,
        )
    else:
        artboard_width = (
            f"constraints.maxWidth < {width_token} ? constraints.maxWidth : {width_token}"
        )
        artboard = scroll_viewport_child_shell(
            width_expr=artboard_width,
            height_token=height_token,
            child=column_widget,
            tolerate_metric_drift=is_tall_mobile_artboard(width, height),
        )
        fallback = wrap_scroll_viewport(
            f"SingleChildScrollView(child: {artboard})",
            theme_variant=theme_variant,
            anchor_top=not responsive_enabled,
        )
    preview_child = artboard_preview_sized_box(child=column_widget)
    return wrap_artboard_preview_layout_builder(
        preview_child=preview_child,
        fallback=fallback,
    )
