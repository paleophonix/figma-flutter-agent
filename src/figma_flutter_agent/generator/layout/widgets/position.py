"""Positioned bounds resolution, viewport wrappers, and stack-position helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.cupertino import wrap_scroll_viewport
from figma_flutter_agent.generator.layout.style import (
    box_decoration_expr,
    has_box_decoration,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
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


def _node_has_nested_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when the clean-tree subtree rooted at ``node`` contains a ``STACK`` node."""
    if node.type == NodeType.STACK:
        return True
    return any(_node_has_nested_stack(child) for child in node.children)


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
    parent_height: float | None = None,
    prefer_top_pin: bool = False,
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
    left = placement.left if placement.left is not None else node.offset_x
    top = placement.top if placement.top is not None else node.offset_y
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
                        horizontal == "CENTER"
                        and placement.left is not None
                        and float(placement.left) > 1.5
                        and float(placement.right) > 1.5
                    )
                )
            ):
                fields[:] = [
                    f"left: {format_geometry_literal(left)}",
                    f"right: {format_geometry_literal(placement.right)}",
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
        elif horizontal == "LEFT_RIGHT":
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
    if node.type != NodeType.CONTAINER or not has_box_decoration(node.style):
        return None
    decoration = box_decoration_expr(
        node.style,
        width=node.sizing.width,
        height=node.sizing.height,
    )
    if decoration is None:
        return None
    from figma_flutter_agent.generator.layout.responsive import responsive_emit_width

    width = responsive_emit_width(node.sizing.width)
    height = node.sizing.height
    if width is not None and width > 0 and height is not None and height > 0:
        leaf = f"Container(width: {width}, height: {height}, decoration: {decoration})"
    elif width is not None and width > 0:
        leaf = f"Container(width: {width}, decoration: {decoration})"
    elif height is not None and height > 0:
        leaf = f"Container(height: {height}, decoration: {decoration})"
    else:
        leaf = f"Container(decoration: {decoration})"
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
        if responsive_enabled and is_mobile_artboard_width(width):
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
        else:
            viewport_align = (
                "Alignment.topLeft" if is_mobile_artboard_width(width) else "Alignment.topCenter"
            )
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
        preview_child = artboard_preview_sized_box(
            child=stack_widget,
            alignment="Alignment.topLeft",
            bounded_child=True,
        )
        return wrap_artboard_preview_layout_builder(
            preview_child=preview_child,
            fallback=fallback,
        )
    artboard = f"SizedBox(width: {width_token}, height: {height_token}, child: {stack_widget})"
    if responsive_enabled:
        from figma_flutter_agent.generator.layout.common import live_scroll_stack_viewport

        fallback = live_scroll_stack_viewport(
            stack_widget=stack_widget,
            artboard_height_token=height_token,
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
    viewport = f"SingleChildScrollView(child: {artboard})"
    return wrap_scroll_viewport(viewport, theme_variant=theme_variant)


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
        wrap_artboard_preview_layout_builder,
    )
    from figma_flutter_agent.generator.layout.cupertino import wrap_scroll_viewport

    width, height = _node_layout_size(node, None)
    if not is_tall_mobile_artboard(width, height):
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
        artboard = (
            f"SizedBox(width: {artboard_width}, height: {height_token}, child: {column_widget})"
        )
        fallback = wrap_scroll_viewport(
            f"SingleChildScrollView(child: {artboard})",
            theme_variant=theme_variant,
        )
    preview_child = artboard_preview_sized_box(child=column_widget)
    return wrap_artboard_preview_layout_builder(
        preview_child=preview_child,
        fallback=fallback,
    )
