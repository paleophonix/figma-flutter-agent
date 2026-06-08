"""Per-node deterministic widget expressions for layout codegen."""

from __future__ import annotations

import math
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar

from figma_flutter_agent.generator.cluster_variants import (
    ClusterVectorVariant,
)
from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.emit_text_span import (
    emit_text_rich,
    emit_text_span_children_from_node,
)
from figma_flutter_agent.generator.figma_anchor import figma_value_key_arg
from figma_flutter_agent.generator.geometry.affine import (
    matrix4_close_suffix,
    matrix4_compose_expr,
    requires_raster_tier,
)
from figma_flutter_agent.generator.layout.common import (
    escape_dart_string,
    normalize_box_constraints,
    wrap_repaint_boundary,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_back_nav_stack as cupertino_wrap_back_nav_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_button_stack as cupertino_wrap_button_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_circular_button_stack as cupertino_wrap_circular_button_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_scroll_viewport,
)
from figma_flutter_agent.generator.layout.form import (
    render_button,
    render_checkbox,
    render_dialog,
    render_dropdown,
    render_input,
    render_radio,
    render_radio_group,
    render_slider,
    render_switch,
    wrap_material_input_child,
)
from figma_flutter_agent.generator.layout.navigation import (
    render_bottom_navigation,
    render_carousel,
    render_tabs,
)
from figma_flutter_agent.generator.layout.responsive import (
    should_apply_responsive_column_reflow,
    wrap_responsive_root_column,
)
from figma_flutter_agent.generator.layout.scroll import (
    render_both_axis_scroll,
    render_grid_view,
    render_scroll_list,
    scroll_axis_for_list,
    wrap_flex_auto_layout_padding,
)
from figma_flutter_agent.generator.layout.style import (
    _shadow_expr,
    border_radius_expr,
    box_decoration_expr,
    box_foreground_decoration_expr,
    card_elevation_expr,
    dart_color_expr,
    has_box_decoration,
    is_dark_fill_color,
    strut_style_expr,
    text_align_expr,
    text_style_expr,
    text_widget_trailing_params,
    wrap_tight_chip_label,
)
from figma_flutter_agent.generator.render_units import (
    format_figma_blur_sigma_literal,
    snap_to_device_pixel,
)
from figma_flutter_agent.generator.variant_props import variant_blocks_interaction
from figma_flutter_agent.parser.interaction import (
    _BACK_NAV_DESCENDANT_DEPTH,
    _descendant_nodes,
    _has_circular_container,
    _is_footer_link_text_node,
    _label_matches_action_hint,
    _local_nodes,
    _stack_spans_primary_button_and_footer_link,
    button_stack_has_left_icon,
    input_children_are_presentational,
    input_flex_value_text,
    input_hint_node,
    input_hint_text,
    input_surface_node,
    input_trailing_chrome_nodes,
    interaction_surface_node,
    is_back_navigation_icon_stack,
    is_link_text,
    looks_like_back_nav_stack,
    looks_like_bottom_docked_sheet,
    looks_like_checkbox_control,
    looks_like_compact_icon_action_button,
    looks_like_compact_icon_action_stack,
    looks_like_password_field_stack,
    looks_like_play_pause_control_stack,
    looks_like_skip_control_stack,
    primary_surface_node,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
    round_geometry,
)
from figma_flutter_agent.parser.render_bounds import (
    child_has_outward_paint,
    stack_needs_soft_clip,
)
from figma_flutter_agent.parser.stack_paint import (
    sort_absolute_stack_children as _sort_absolute_stack_children,
)
from figma_flutter_agent.schemas import (
    AxisPins,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    SizingMode,
    StackPlacement,
    WrapKind,
)

_MAIN_AXIS = {
    "start": "MainAxisAlignment.start",
    "end": "MainAxisAlignment.end",
    "center": "MainAxisAlignment.center",
    "spaceBetween": "MainAxisAlignment.spaceBetween",
    "stretch": "MainAxisAlignment.spaceBetween",
    "baseline": "MainAxisAlignment.start",
}

_CROSS_AXIS = {
    "start": "CrossAxisAlignment.start",
    "end": "CrossAxisAlignment.end",
    "center": "CrossAxisAlignment.center",
    "spaceBetween": "CrossAxisAlignment.center",
    "stretch": "CrossAxisAlignment.stretch",
    "baseline": "CrossAxisAlignment.baseline",
}

_ICON_BUTTON_MAX_SIZE = 80.0
_OVERLAY_TEXT_MAX_SIZE = 60.0

_snap_device_pixels_ctx: ContextVar[bool] = ContextVar(
    "snap_device_pixels", default=False
)


@contextmanager
def snap_device_pixels_scope(enabled: bool):
    """Enable logical-to-physical pixel snapping for positioned layout emit (FID-45)."""
    token = _snap_device_pixels_ctx.set(enabled)
    try:
        yield
    finally:
        _snap_device_pixels_ctx.reset(token)


def _is_skip_control_stack(parent_node: CleanDesignTreeNode) -> bool:
    """Detect skip/rewind stacks that pair an arc vector with a numeric label."""
    if parent_node.type != NodeType.STACK:
        return False
    has_vector = any(
        child.type == NodeType.VECTOR
        and (child.vector_asset_key or child.style.has_stroke)
        for child in parent_node.children
    )
    has_numeric = any(
        child.type == NodeType.TEXT and (child.text or "").strip().isdigit()
        for child in parent_node.children
    )
    return has_vector and has_numeric


def _effective_svg_dimensions(
    node: CleanDesignTreeNode,
    width: float | None,
    height: float | None,
) -> tuple[float | None, float | None]:
    """Ensure stroke-only SVG exports remain visible when Figma bbox height/width is ~0."""
    if not node.style.has_stroke:
        return width, height
    stroke = node.style.border_width or 3.0
    min_dim = max(stroke, 3.0)
    if width is not None and height is not None:
        if width >= min_dim * 4 and height < min_dim:
            height = min_dim
        elif height >= min_dim * 4 and width < min_dim:
            width = min_dim
    elif width is not None and width < min_dim:
        width = min_dim
    elif height is not None and height < min_dim:
        height = min_dim
    return width, height


def _stroke_line_top_adjustment(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
    render_height: float | None,
) -> float | None:
    """Center expanded stroke-line bounds on the original Figma baseline."""
    if not node.style.has_stroke or placement.top is None or render_height is None:
        return placement.top
    raw_height = node.sizing.height or 0.0
    if raw_height >= render_height:
        return placement.top
    adjusted = placement.top - (render_height - raw_height) / 2.0
    return round_geometry(adjusted) or 0.0


_SKIP_NUMERAL_DOWN_NUDGE = 2.5


def _skip_control_numeral_top(
    parent_node: CleanDesignTreeNode,
    text_node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> float:
    """Vertically center skip numerals inside the arc with a small optical nudge."""
    parent_height = parent_node.sizing.height or 0.0
    text_height = text_node.sizing.height or placement.height or 0.0
    if parent_height <= 0 or text_height <= 0:
        return placement.top or 0.0
    adjusted = (parent_height - text_height) / 2.0 + _SKIP_NUMERAL_DOWN_NUDGE
    return round_geometry(adjusted) or 0.0


def _slider_thumb_top(
    outer: CleanDesignTreeNode,
    siblings: list[CleanDesignTreeNode],
    default_top: float,
) -> float:
    """Align slider thumbs to the visual center of a sibling progress stroke."""
    outer_height = outer.sizing.height or 17.0
    outer_left = outer.stack_placement.left if outer.stack_placement else 0.0
    outer_right = outer_left + (outer.sizing.width or outer_height)
    for sibling in siblings:
        if (
            sibling.id == outer.id
            or sibling.type != NodeType.VECTOR
            or not sibling.style.has_stroke
        ):
            continue
        placement = sibling.stack_placement
        if placement is None:
            continue
        track_left = placement.left or 0.0
        track_width = sibling.sizing.width or 0.0
        track_right = track_left + track_width
        if track_right < outer_left - 8.0 or track_left > outer_right + 8.0:
            continue
        _track_width, effective_height = _effective_svg_dimensions(
            sibling,
            sibling.sizing.width,
            sibling.sizing.height,
        )
        effective_height = effective_height or 3.0
        raw_height = sibling.sizing.height or 0.0
        line_top = placement.top or 0.0
        if raw_height < effective_height:
            line_top -= (effective_height - raw_height) / 2.0
        line_center = line_top + effective_height / 2.0
        adjusted = line_center - outer_height / 2.0
        return round_geometry(adjusted) or 0.0
    return default_top


def _svg_fit_mode(
    node: CleanDesignTreeNode,
    width: float | None,
    height: float | None,
) -> str:
    """Choose BoxFit for exported SVG assets."""
    if node.style.has_stroke and node.style.background_color is None:
        if width and height and (width < 4.0 or height < 4.0):
            return "BoxFit.fill"
        return "BoxFit.contain"
    if (
        width
        and height
        and width > 0
        and height > 0
        and node.sizing.width
        and node.sizing.height
        and node.sizing.width > 0
        and node.sizing.height > 0
    ):
        box_aspect = width / height
        design_aspect = node.sizing.width / node.sizing.height
        if abs(box_aspect - design_aspect) > 0.12:
            return "BoxFit.contain"
    return "BoxFit.fill" if width and height else "BoxFit.contain"


SVG_PATH_RASTER_THRESHOLD = 120


def _vector_needs_baked_raster(node: CleanDesignTreeNode) -> bool:
    """Return True when an exported vector should prefer a baked PNG raster (FID-46)."""
    if (
        node.style.layer_blur
        or node.style.background_blur
        or node.vector_svg_has_filter
    ):
        return True
    if node.style.has_stroke and node.style.stroke_dash_pattern:
        return True
    if (
        node.vector_svg_path_count is not None
        and node.vector_svg_path_count > SVG_PATH_RASTER_THRESHOLD
    ):
        return True
    return len(node.children) > 1


def _render_exported_vector(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
) -> str | None:
    """Render an exported vector asset per spec (SVG, or baked PNG for blur/filter)."""
    width, height = _node_layout_size(node, node.stack_placement)
    width, height = _effective_svg_dimensions(node, width, height)

    if node.image_asset_key and _vector_needs_baked_raster(node):
        asset = escape_dart_string(node.image_asset_key)
        params = [f"'{asset}'"]
        if width is not None and width > 0:
            params.append(f"width: {width}")
        if height is not None and height > 0:
            params.append(f"height: {height}")
        params.append("fit: BoxFit.fill")
        return f"Image.asset({', '.join(params)})"

    if node.vector_asset_key and uses_svg and node.vector_asset_key.endswith(".svg"):
        return _render_svg_picture(node, escape_dart_string(node.vector_asset_key))

    if node.image_asset_key:
        asset = escape_dart_string(node.image_asset_key)
        params = [f"'{asset}'"]
        if width is not None and width > 0:
            params.append(f"width: {width}")
        if height is not None and height > 0:
            params.append(f"height: {height}")
        params.append("fit: BoxFit.fill")
        return f"Image.asset({', '.join(params)})"

    return None


def _should_prefer_exported_svg(node: CleanDesignTreeNode) -> bool:
    """Prefer baked SVG exports over native gradients when rotation or gradients differ."""
    if node.vector_asset_key is None:
        return False
    if node.type in {NodeType.VECTOR, NodeType.IMAGE}:
        return True
    if node.render_boundary:
        return True
    if (
        not node.children
        and node.cluster_id
        and node.type in {NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}
    ):
        return True
    if node.type != NodeType.CONTAINER:
        return False
    if node.style.gradient is not None:
        return True
    return _node_rotation_rad(node) is not None and abs(_node_rotation_rad(node) or 0.0) > 1e-3


def _is_roughly_square(width: float, height: float, *, max_size: float) -> bool:
    """Return True when a frame is square-ish and small enough to be an icon button."""
    if width <= 0 or height <= 0 or width > max_size or height > max_size:
        return False
    return abs(width - height) <= max(8.0, min(width, height) * 0.15)


def _is_composite_icon_stack(parent_node: CleanDesignTreeNode) -> bool:
    """Return True when a small stack layers multiple absolute vectors (e.g. Google G)."""
    if parent_node.type != NodeType.STACK:
        return False
    vectors = [
        child
        for child in parent_node.children
        if child.type == NodeType.VECTOR and child.stack_placement is not None
    ]
    if len(vectors) < 2:
        return False
    parent_width = parent_node.sizing.width
    parent_height = parent_node.sizing.height
    if parent_width is None or parent_height is None:
        return False
    return (
        parent_width <= _ICON_BUTTON_MAX_SIZE and parent_height <= _ICON_BUTTON_MAX_SIZE
    )


def _should_center_in_parent_stack(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Detect icons and overlay numerals that should fill and center in a Stack parent."""
    if parent_node is None or parent_node.type != NodeType.STACK:
        return False
    if _is_composite_icon_stack(parent_node):
        return False
    if _is_skip_control_stack(parent_node):
        return False
    parent_width = parent_node.sizing.width
    parent_height = parent_node.sizing.height
    if (
        parent_width is None
        or parent_height is None
        or parent_width <= 0
        or parent_height <= 0
    ):
        return False

    if node.type in {NodeType.VECTOR, NodeType.IMAGE}:
        node_width = node.sizing.width
        node_height = node.sizing.height
        if node_width is None or node_height is None:
            return False
        if node_width >= parent_width * 0.85 or node_height >= parent_height * 0.85:
            return False
        return _is_roughly_square(
            parent_width, parent_height, max_size=_ICON_BUTTON_MAX_SIZE
        )

    if node.type == NodeType.TEXT:
        if not _is_roughly_square(
            parent_width, parent_height, max_size=_OVERLAY_TEXT_MAX_SIZE
        ):
            return False
        text = (node.text or "").strip()
        return bool(text) and text.isdigit() and len(text) <= 4
    return False


def _clamp_centered_text_to_parent_stack(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> CleanDesignTreeNode:
    """Cap centered labels to their parent stack width for absolute title rows."""
    from figma_flutter_agent.parser.layout import round_geometry

    if (
        node.type != NodeType.TEXT
        or node.style.text_align != "CENTER"
        or parent_node is None
        or parent_node.type != NodeType.STACK
    ):
        return node
    parent_width = parent_node.sizing.width
    if parent_width is None or parent_width <= 0:
        return node
    placement = node.stack_placement
    if placement is None:
        return node
    cap = float(parent_width)
    current_width = (
        placement.width if placement.width is not None else node.sizing.width
    )
    if current_width is None or float(current_width) <= cap + 0.5:
        return node
    rounded = round_geometry(cap)
    return node.model_copy(
        update={
            "stack_placement": placement.model_copy(
                update={
                    "left": 0.0,
                    "right": 0.0,
                    "width": rounded,
                    "horizontal": "LEFT_RIGHT",
                },
            ),
            "sizing": node.sizing.model_copy(
                update={"width": cap, "width_mode": SizingMode.FIXED},
            ),
        },
    )


def _wrap_centered_stack_child(node: CleanDesignTreeNode, widget: str) -> str:
    """Center a child within a square Stack using optional glyph offset padding."""
    if node.type != NodeType.TEXT:
        return f"Center(child: {widget})"
    if len((node.text or node.name or "").strip()) <= 1:
        return f"Center(child: {widget})"
    glyph_offset = node.style.glyph_top_offset
    if glyph_offset is not None and glyph_offset > 0:
        padding_top = round(min(glyph_offset, 4.0), 1)
        return (
            "Center("
            f"child: Padding(padding: const EdgeInsets.only(top: {padding_top}), child: {widget})"
            ")"
        )
    return f"Center(child: {widget})"


_PI_ROTATION = 3.141592653589793
_TWO_PI = 2.0 * _PI_ROTATION
_COMPACT_NAV_ICON_MAX_PX = 32.0


def _node_rotation_rad(node: CleanDesignTreeNode) -> float | None:
    """Return rotation in radians for Flutter ``Transform.rotate`` emit."""
    if node.rotation_rad is not None:
        return node.rotation_rad
    if node.rotation is None:
        return None
    if abs(node.rotation) <= _TWO_PI + 0.01:
        return node.rotation
    return math.radians(node.rotation)


def _skip_redundant_pi_vector_rotation(node: CleanDesignTreeNode) -> bool:
    """Omit π rotations on compact vectors where SVG export already bakes orientation."""
    angle = _node_rotation_rad(node)
    if angle is None or abs(angle) < 1e-3:
        return False
    if abs(abs(angle) - _PI_ROTATION) >= 0.25:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    return (
        width <= _COMPACT_NAV_ICON_MAX_PX
        and height <= _COMPACT_NAV_ICON_MAX_PX
        and bool(node.vector_asset_key)
    )


def _apply_node_transform(node: CleanDesignTreeNode, widget: str) -> str:
    """Apply Figma rotation/affine using Matrix4 when geometry planner attached (T1)."""
    slot = node.layout_slot
    transform = slot.residual_matrix if slot is not None else None
    if transform is not None and not requires_raster_tier(transform):
        prefix = matrix4_compose_expr(transform)
        if prefix is not None:
            return f"{prefix}{widget}{matrix4_close_suffix()}"
    angle_rad = _node_rotation_rad(node)
    if angle_rad is None or abs(angle_rad) < 1e-3:
        return widget
    if _skip_redundant_pi_vector_rotation(node):
        return widget
    angle = format_micro_style_literal(angle_rad)
    placement = node.stack_placement
    width = node.sizing.width or (placement.width if placement else None)
    height = node.sizing.height or (placement.height if placement else None)
    if width and height and width > 0 and height > 0:
        half_w = format_geometry_literal(width / 2.0)
        half_h = format_geometry_literal(height / 2.0)
        return (
            f"Transform.translate("
            f"offset: Offset({half_w}, {half_h}), "
            f"child: Transform.rotate(angle: {angle}, child: Transform.translate("
            f"offset: Offset(-{half_w}, -{half_h}), child: {widget})))"
        )
    return (
        f"Transform.rotate(angle: {angle}, "
        f"alignment: Alignment.center, child: {widget})"
    )


_ICON_RAIL_GLYPH_SIZE = 20.0
_ICON_RAIL_FRAME_MIN = 40.0
_ICON_RAIL_FRAME_MAX = 56.0


def _clamp_svg_dimensions_for_icon_rail(
    width: float | None,
    height: float | None,
) -> tuple[float | None, float | None]:
    """Shrink square SVG exports that fill an icon rail instead of the glyph box."""
    if width is None or height is None or width <= 0 or height <= 0:
        return width, height
    if abs(float(width) - float(height)) > 1.0:
        return width, height
    size = float(width)
    if _ICON_RAIL_FRAME_MIN <= size <= _ICON_RAIL_FRAME_MAX and size > _ICON_RAIL_GLYPH_SIZE + 2.0:
        return _ICON_RAIL_GLYPH_SIZE, _ICON_RAIL_GLYPH_SIZE
    return width, height


def _render_svg_picture(node: CleanDesignTreeNode, asset: str) -> str:
    """Render an SVG asset with explicit bounds when Figma provides them."""
    width, height = _node_layout_size(node, node.stack_placement)
    width, height = _effective_svg_dimensions(node, width, height)
    width, height = _clamp_svg_dimensions_for_icon_rail(width, height)
    params = [f"'{asset}'"]
    if width is not None and width > 0:
        params.append(f"width: {width}")
    if height is not None and height > 0:
        params.append(f"height: {height}")
    fit = _svg_fit_mode(node, width, height)
    params.append(f"fit: {fit}")
    widget = f"SvgPicture.asset({', '.join(params)})"
    return _apply_node_transform(node, widget)


def _render_native_blur_vector(node: CleanDesignTreeNode) -> str:
    """Render blurred vectors with ``ImageFiltered`` when assets are unavailable (FID-41)."""
    width, height = _node_layout_size(node, node.stack_placement)
    blur = node.style.layer_blur or node.style.background_blur or 35.0
    sigma = format_figma_blur_sigma_literal(blur)
    color = node.style.background_color or "0xFFFFFFFF"
    opacity = 0.55
    size_parts: list[str] = []
    if width is not None and width > 0:
        size_parts.append(f"width: {width}")
    if height is not None and height > 0:
        size_parts.append(f"height: {height}")
    if (
        width is not None
        and height is not None
        and width > 0
        and height > 0
        and abs(width - height) <= max(2.0, min(width, height) * 0.02)
    ):
        shape = "shape: BoxShape.circle, "
    elif width is not None and height is not None and width > 0 and height > 0:
        shape = f"borderRadius: BorderRadius.all(Radius.elliptical({width / 2.0}, {height / 2.0})), "
    else:
        shape = ""
    size_prefix = f"{', '.join(size_parts)}, " if size_parts else ""
    inner = (
        f"Container({size_prefix}"
        f"decoration: BoxDecoration({shape}"
        f"color: const Color({color}).withOpacity({opacity})))"
    )
    widget = (
        f"ImageFiltered("
        f"imageFilter: ImageFilter.blur(sigmaX: {sigma}, sigmaY: {sigma}), "
        f"child: {inner})"
    )
    angle_rad = _node_rotation_rad(node)
    if angle_rad is not None and abs(angle_rad) > 1e-3:
        angle = format_micro_style_literal(angle_rad)
        return (
            f"Transform.rotate(angle: {angle}, "
            f"alignment: Alignment.topLeft, child: {widget})"
        )
    return widget


def _circle_container_metrics(
    node: CleanDesignTreeNode,
) -> tuple[float, float, float] | None:
    """Return center coordinates and diameter for circular container nodes."""
    width = node.sizing.width
    height = node.sizing.height
    if node.type != NodeType.CONTAINER or width is None or height is None:
        return None
    if width <= 0 or height <= 0:
        return None
    if not _is_roughly_square(width, height, max_size=9999.0):
        return None
    radius = node.style.border_radius
    if radius is not None and radius < min(width, height) / 2.0 - 1.0:
        return None
    placement = node.stack_placement
    center_x = (placement.left if placement is not None else 0.0) + width / 2.0
    center_y = (placement.top if placement is not None else 0.0) + height / 2.0
    return center_x, center_y, max(width, height)


def _find_concentric_circle_pair(
    children: list[CleanDesignTreeNode],
) -> tuple[CleanDesignTreeNode, CleanDesignTreeNode] | None:
    """Find two concentric circular containers used as a slider thumb ring + core."""
    circles: list[tuple[CleanDesignTreeNode, float, float, float]] = []
    for child in children:
        if child.stack_placement is None:
            continue
        metrics = _circle_container_metrics(child)
        if metrics is None:
            continue
        center_x, center_y, size = metrics
        circles.append((child, center_x, center_y, size))
    for index, (first, ax, ay, first_size) in enumerate(circles):
        for second, bx, by, second_size in circles[index + 1 :]:
            if abs(ax - bx) > 3.0 or abs(ay - by) > 3.0:
                continue
            if abs(first_size - second_size) <= 1.0:
                continue
            first_color = first.style.background_color or ""
            second_color = second.style.background_color or ""
            if first_color != second_color:
                continue
            if first_size >= second_size:
                return first, second
            return second, first
    return None


def _render_concentric_circle_thumb(
    outer: CleanDesignTreeNode,
    inner: CleanDesignTreeNode,
    *,
    stack_siblings: list[CleanDesignTreeNode] | None = None,
) -> list[str]:
    """Render a slider thumb as an outer ring plus inner filled circle."""
    outer_width = outer.sizing.width or 14.0
    outer_height = outer.sizing.height or 14.0
    inner_width = inner.sizing.width or 10.0
    inner_height = inner.sizing.height or 10.0
    color = inner.style.background_color or outer.style.background_color or "0xFF3F414E"
    outer_placement = outer.stack_placement
    left = (
        outer_placement.left
        if outer_placement and outer_placement.left is not None
        else 0.0
    )
    top = (
        outer_placement.top
        if outer_placement and outer_placement.top is not None
        else 0.0
    )
    if stack_siblings is not None:
        top = _slider_thumb_top(outer, stack_siblings, top)
    inner_left = left + (outer_width - inner_width) / 2.0
    inner_top = top + (outer_height - inner_height) / 2.0
    return [
        (
            f"Positioned(left: {format_geometry_literal(left)}, "
            f"top: {format_geometry_literal(top)}, "
            f"width: {format_geometry_literal(outer_width)}, "
            f"height: {format_geometry_literal(outer_height)}, "
            "child: Container("
            "decoration: BoxDecoration("
            f"color: const Color({color}).withOpacity(0.24), shape: BoxShape.circle)))"
        ),
        (
            f"Positioned(left: {format_geometry_literal(inner_left)}, "
            f"top: {format_geometry_literal(inner_top)}, "
            f"width: {format_geometry_literal(inner_width)}, "
            f"height: {format_geometry_literal(inner_height)}, "
            "child: Container("
            "decoration: const BoxDecoration("
            f"color: Color({color}), shape: BoxShape.circle)))"
        ),
    ]


def _render_svg_picture_variant(
    node: CleanDesignTreeNode,
    *,
    forward_asset: str,
    backward_asset: str,
    param_name: str,
) -> str:
    """Render an SVG asset that switches by a boolean cluster variant parameter."""
    width, height = _node_layout_size(node, node.stack_placement)
    width, height = _effective_svg_dimensions(node, width, height)
    forward = escape_dart_string(forward_asset)
    backward = escape_dart_string(backward_asset)
    params = [f"{param_name} ? '{forward}' : '{backward}'"]
    if width is not None and width > 0:
        params.append(f"width: {width}")
    if height is not None and height > 0:
        params.append(f"height: {height}")
    fit = _svg_fit_mode(node, width, height)
    params.append(f"fit: {fit}")
    return f"SvgPicture.asset({', '.join(params)})"


def _vertical_bar_containers(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Collect narrow vertical bars used by play/pause controls."""
    bars: list[CleanDesignTreeNode] = []

    def walk(current: CleanDesignTreeNode) -> None:
        if current.type == NodeType.CONTAINER:
            width = current.sizing.width
            height = current.sizing.height
            if (
                width is not None
                and height is not None
                and width <= 10.0
                and height >= 15.0
            ):
                bars.append(current)
        for child in current.children:
            walk(child)

    walk(node)
    return bars


def _largest_circle_container(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the largest circular container within ``node``."""
    best: CleanDesignTreeNode | None = None
    best_size = 0.0

    def walk(current: CleanDesignTreeNode) -> None:
        nonlocal best, best_size
        metrics = _circle_container_metrics(current)
        if metrics is None:
            for child in current.children:
                walk(child)
            return
        _center_x, _center_y, size = metrics
        if size > best_size:
            best_size = size
            best = current
        for child in current.children:
            walk(child)

    walk(node)
    return best


def _is_play_pause_dark_fill(fill: str | None) -> bool:
    """Return True for visually dark fills used by play/pause button cores."""
    return is_dark_fill_color(fill)


def _collect_background_fills(node: CleanDesignTreeNode) -> list[str]:
    fills: list[str] = []

    def walk(current: CleanDesignTreeNode) -> None:
        if current.style.background_color:
            fills.append(current.style.background_color)
        for child in current.children:
            walk(child)

    walk(node)
    return fills


def _node_stack_bounds(
    node: CleanDesignTreeNode,
) -> tuple[float, float, float, float] | None:
    """Return left/top/right/bottom for an absolutely placed node."""
    placement = node.stack_placement
    width = node.sizing.width
    height = node.sizing.height
    if (
        placement is None
        or width is None
        or height is None
        or width <= 0
        or height <= 0
    ):
        return None
    left = placement.left or 0.0
    top = placement.top or 0.0
    return left, top, left + width, top + height


def _play_pause_palette(node: CleanDesignTreeNode) -> tuple[str, str, str] | None:
    """Return outer ring, core, and bar fills sampled from the control subtree."""
    fills = _collect_background_fills(node)
    if not fills:
        return None
    dark_fills = [fill for fill in fills if _is_play_pause_dark_fill(fill)]
    light_fills = [fill for fill in fills if fill not in dark_fills]
    if not dark_fills:
        return None
    core_color = dark_fills[0]
    ring_color = light_fills[0] if light_fills else core_color
    bar_color = light_fills[-1] if light_fills else ring_color
    return ring_color, core_color, bar_color


def _play_pause_core_spec(node: CleanDesignTreeNode) -> tuple[float, str] | None:
    """Return the dark core diameter and fill for a play/pause control."""
    palette = _play_pause_palette(node)
    fallback_core = palette[1] if palette is not None else "0xFF3F414E"
    best_diameter = 0.0
    best_color = fallback_core
    segments: list[tuple[float, float, float, float]] = []

    def walk(current: CleanDesignTreeNode) -> None:
        nonlocal best_diameter, best_color
        width = current.sizing.width
        height = current.sizing.height
        if (
            current.type == NodeType.STACK
            and width is not None
            and height is not None
            and 70.0 <= min(width, height) <= 100.0
            and _is_roughly_square(width, height, max_size=9999.0)
        ):
            dark_children = [
                child
                for child in current.children
                if child.type in {NodeType.VECTOR, NodeType.CONTAINER}
                and _is_play_pause_dark_fill(child.style.background_color)
            ]
            if len(dark_children) >= 2:
                size = max(width, height)
                if size > best_diameter:
                    best_diameter = size
                    best_color = dark_children[0].style.background_color or best_color

        bounds = _node_stack_bounds(current)
        if bounds is not None and _is_play_pause_dark_fill(
            current.style.background_color
        ):
            left, top, right, bottom = bounds
            if min(right - left, bottom - top) >= 20.0:
                segments.append(bounds)
                fill = current.style.background_color or best_color
                if max(right - left, bottom - top) > best_diameter:
                    best_color = fill

        if (
            current.type in {NodeType.CONTAINER, NodeType.VECTOR}
            and width is not None
            and height is not None
            and min(width, height) >= 35.0
            and _is_roughly_square(width, height, max_size=9999.0)
            and _is_play_pause_dark_fill(current.style.background_color)
        ):
            size = max(width, height)
            if size > best_diameter:
                best_diameter = size
                best_color = current.style.background_color or best_color

        for child in current.children:
            walk(child)

    walk(node)

    if segments:
        min_left = min(segment[0] for segment in segments)
        min_top = min(segment[1] for segment in segments)
        max_right = max(segment[2] for segment in segments)
        max_bottom = max(segment[3] for segment in segments)
        union_diameter = max(max_right - min_left, max_bottom - min_top)
        if union_diameter > best_diameter:
            best_diameter = union_diameter

    if best_diameter <= 0.0:
        return None
    return best_diameter, best_color


def _find_play_pause_core(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Find a representative dark core node inside a play/pause control stack."""
    spec = _play_pause_core_spec(node)
    if spec is None:
        return None
    best: CleanDesignTreeNode | None = None
    best_size = 0.0

    def walk(current: CleanDesignTreeNode) -> None:
        nonlocal best, best_size
        bounds = _node_stack_bounds(current)
        if bounds is not None and _is_play_pause_dark_fill(
            current.style.background_color
        ):
            left, top, right, bottom = bounds
            size = max(right - left, bottom - top)
            if size > best_size:
                best_size = size
                best = current
        for child in current.children:
            walk(child)

    walk(node)
    return best


def _sizing_like_skip_control(node: CleanDesignTreeNode) -> bool:
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    return 28.0 <= width <= 56.0 and 28.0 <= height <= 56.0


def _try_render_pruned_cluster_skip_control(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    skip_cluster_id: str | None,
    cluster_vector_variant: ClusterVectorVariant | None,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Re-render a deduped skip/rewind cluster whose children were pruned away."""
    if node.children and not node.vector_asset_key:
        return None
    if skip_cluster_id is not None and node.cluster_id == skip_cluster_id:
        return None
    if not _sizing_like_skip_control(node):
        return None
    asset = node.vector_asset_key
    if asset is None and cluster_vector_variant is not None:
        from figma_flutter_agent.generator.cluster_variants import (
            cluster_skip_backward_by_placement,
        )

        asset = (
            cluster_vector_variant.backward_asset
            if cluster_skip_backward_by_placement(node)
            else cluster_vector_variant.forward_asset
        )
    if asset is None or not uses_svg:
        return None
    svg = _render_svg_picture(node, escape_dart_string(asset))
    numeral = "15"
    style_expr = text_style_expr(
        node,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if "fontSize:" not in style_expr:
        style_expr = (
            "Theme.of(context).textTheme.bodyMedium?.copyWith("
            "color: Color(0xFFA0A3B1), fontSize: 12.0, fontWeight: FontWeight.w500)"
        )
    placement = node.stack_placement
    numeral_top = (
        _skip_control_numeral_top(node, node, placement) if placement else 15.5
    )
    body = (
        "Stack(clipBehavior: Clip.none, children: ["
        f"Positioned(left: 0.0, top: 0.0, width: {format_geometry_literal(node.sizing.width or 38.8)}, "
        f"height: {format_geometry_literal(node.sizing.height or 39.0)}, "
        f"child: Semantics(label: 'Vector', child: {svg})), "
        "Positioned("
        f"left: 11.4, top: {format_geometry_literal(numeral_top)}, width: 15.9, height: 13.0, "
        f"child: Semantics(label: '{numeral}', child: Center(child: Text('{numeral}', "
        f"style: {style_expr}, textScaler: textScaler, textAlign: TextAlign.center))))"
        "])"
    )
    return _wrap_button_stack(body, node, theme_variant=theme_variant)


def _playback_seek_vector_ids(node: CleanDesignTreeNode) -> set[str]:
    if node.type != NodeType.STACK:
        return set()
    has_timestamps = any(
        child.type == NodeType.TEXT
        and child.text
        and ":" in child.text
        and len(child.text.strip()) <= 8
        for child in node.children
    )
    if not has_timestamps:
        return set()
    vectors = [
        child
        for child in node.children
        if child.type == NodeType.VECTOR or child.vector_asset_key
    ]
    if len(vectors) < 2:
        return set()
    wide = max(vectors, key=lambda item: float(item.sizing.width or 0))
    if float(wide.sizing.width or 0) < 200.0:
        return set()
    narrow = [item for item in vectors if item.id != wide.id]
    ids = {wide.id}
    if narrow:
        thumb = min(narrow, key=lambda item: float(item.sizing.width or 0))
        ids.add(thumb.id)
    return ids


def _playback_seek_omit_child_ids(node: CleanDesignTreeNode) -> set[str]:
    """Drop Figma track/thumb decorations when a native ``Slider`` replaces them."""
    if not _playback_seek_vector_ids(node):
        return set()
    omit: set[str] = set()
    for child in node.children:
        if child.type in {NodeType.VECTOR, NodeType.SLIDER}:
            omit.add(child.id)
            continue
        if (
            child.type == NodeType.CONTAINER
            and _circle_container_metrics(child) is not None
        ):
            omit.add(child.id)
    return omit


def _should_suppress_playback_slider_node(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Skip duplicate progress ``SLIDER`` instances when a media row already has one."""
    if node.type != NodeType.SLIDER:
        return False
    width = float(node.sizing.width or 0)
    if width < 200.0:
        return False
    if parent_node is None:
        return False
    if parent_node.type == NodeType.STACK and _playback_seek_vector_ids(parent_node):
        return True
    if parent_node.type != NodeType.STACK:
        return False
    for sibling in parent_node.children:
        if sibling.id == node.id:
            continue
        if sibling.type == NodeType.STACK and _playback_seek_vector_ids(sibling):
            return True
    return False


def _playback_slider_value(node: CleanDesignTreeNode) -> str:
    start_seconds = 0.0
    total_seconds = 45.0 * 60.0
    for child in node.children:
        if child.type != NodeType.TEXT or not child.text or ":" not in child.text:
            continue
        parts = child.text.strip().split(":", maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            minutes = int(parts[0])
            seconds = int(parts[1])
        except ValueError:
            continue
        elapsed = minutes * 60 + seconds
        if child.stack_placement is not None and (child.stack_placement.left or 0) < 80:
            start_seconds = float(elapsed)
        else:
            total_seconds = max(float(elapsed), 1.0)
    ratio = min(1.0, max(0.0, start_seconds / total_seconds))
    return format_geometry_literal(ratio)


def _render_playback_seek_slider(node: CleanDesignTreeNode) -> str | None:
    vector_ids = _playback_seek_vector_ids(node)
    if not vector_ids:
        return None
    track = max(
        (child for child in node.children if child.id in vector_ids),
        key=lambda item: float(item.sizing.width or 0),
    )
    placement = track.stack_placement
    width = (placement.width if placement is not None else None) or track.sizing.width
    if width is None or width <= 0:
        return None
    stack_width = float(node.sizing.width or 0.0)
    if stack_width > float(width):
        width = stack_width
    left = 0.0
    top = placement.top if placement is not None and placement.top is not None else 0.0
    value = _playback_slider_value(node)
    slider = (
        f"Slider("
        f"value: {value}, "
        f"onChanged: (value) {{ {inline_custom_code_comment(custom_code_zone_id(track.id, 'slider-action'))} }}"
        ")"
    )
    fields = [
        f"left: {format_geometry_literal(left)}",
        f"top: {format_geometry_literal(top)}",
        f"width: {format_geometry_literal(width)}",
        f"{figma_value_key_arg(track.id)}",
        f"child: {slider}",
    ]
    return f"Positioned({', '.join(fields)})"


def _render_synthetic_play_pause_control(node: CleanDesignTreeNode) -> str:
    """Native play/pause when vectors were collapsed into a render boundary."""
    width = float(node.sizing.width or 109.0)
    height = float(node.sizing.height or 109.0)
    core_width = min(width, height) * 0.81
    core_color = "0xFF3F414E"
    ring_color = "0xFFB6B8BE"
    bar_color = "0xFFFFFFFF"
    bar_width = 6.5
    bar_height = 24.0
    outer_size = max(width, height)
    return (
        f"SizedBox(width: {width}, height: {height}, child: Stack("
        "alignment: Alignment.center, "
        "children: ["
        f"Container(width: {outer_size}, height: {outer_size}, decoration: BoxDecoration("
        f"color: Color({ring_color}).withOpacity(0.35), shape: BoxShape.circle)), "
        f"Container(width: {core_width}, height: {core_width}, decoration: BoxDecoration("
        f"color: Color({core_color}), shape: BoxShape.circle)), "
        "Row(mainAxisSize: MainAxisSize.min, children: ["
        f"Container(width: {bar_width}, height: {bar_height}, decoration: BoxDecoration("
        f"color: Color({bar_color}), borderRadius: BorderRadius.circular(14.0))), "
        "const SizedBox(width: 6.0), "
        f"Container(width: {bar_width}, height: {bar_height}, decoration: BoxDecoration("
        f"color: Color({bar_color}), borderRadius: BorderRadius.circular(14.0)))"
        "])])"
        ")"
    )


def _try_render_play_pause_stack(node: CleanDesignTreeNode) -> str | None:
    """Render native play/pause controls instead of fragile multi-vector SVG stacks."""
    if node.type != NodeType.STACK:
        return None
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width < 70.0 or height < 70.0:
        return None
    if width > 150.0 or height > 150.0:
        return None
    bars = _vertical_bar_containers(node)
    if len(bars) < 2:
        if node.render_boundary and looks_like_play_pause_control_stack(node):
            return _render_synthetic_play_pause_control(node)
        return None
    core_spec = _play_pause_core_spec(node)
    if core_spec is None:
        return None
    core_width, core_color = core_spec
    palette = _play_pause_palette(node)
    ring_color = palette[0] if palette is not None else core_color
    bar_color = (
        palette[2]
        if palette is not None
        else (bars[0].style.background_color or ring_color)
    )
    bar_width = bars[0].sizing.width or 6.5
    bar_height = bars[0].sizing.height or 24.0
    outer_size = max(width, height)
    return (
        f"SizedBox(width: {width}, height: {height}, child: Stack("
        "alignment: Alignment.center, "
        "children: ["
        f"Container(width: {outer_size}, height: {outer_size}, decoration: BoxDecoration("
        f"color: Color({ring_color}).withOpacity(0.35), shape: BoxShape.circle)), "
        f"Container(width: {core_width}, height: {core_width}, decoration: BoxDecoration("
        f"color: Color({core_color}), shape: BoxShape.circle)), "
        "Row(mainAxisSize: MainAxisSize.min, children: ["
        f"Container(width: {bar_width}, height: {bar_height}, decoration: BoxDecoration("
        f"color: Color({bar_color}), borderRadius: BorderRadius.circular(14.0))), "
        "const SizedBox(width: 6.0), "
        f"Container(width: {bar_width}, height: {bar_height}, decoration: BoxDecoration("
        f"color: Color({bar_color}), borderRadius: BorderRadius.circular(14.0)))"
        "])])"
        ")"
    )


def _flex_parent_data_wrapper(widget: str) -> bool:
    """Return True when ``widget`` is already an ``Expanded`` / ``Flexible`` wrapper."""
    trimmed = widget.lstrip()
    return trimmed.startswith(
        ("Expanded(", "Flexible(", "const Expanded(", "const Flexible(")
    )


def _extract_balanced_prefix_child(source: str, child_start: int) -> str | None:
    """Return the balanced child expression starting at ``child_start``."""
    depth = 0
    for index in range(child_start, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return source[child_start:index]
            depth -= 1
    return None


def _unwrap_flex_parent_data_wrapper(widget: str) -> tuple[str, str] | None:
    """Return ``(wrapper_prefix, inner)`` for a top-level Expanded/Flexible wrapper."""
    trimmed = widget.lstrip()
    for marker in (
        "Expanded(child: ",
        "Flexible(fit: FlexFit.loose, flex: 0, child: ",
        "Flexible(fit: FlexFit.loose, child: ",
        "Flexible(child: ",
        "const Expanded(child: ",
        "const Flexible(fit: FlexFit.loose, flex: 0, child: ",
        "const Flexible(fit: FlexFit.loose, child: ",
        "const Flexible(child: ",
    ):
        if trimmed.startswith(marker):
            inner = _extract_balanced_prefix_child(trimmed, len(marker))
            if inner is not None:
                return marker, inner
    return None


def _hoist_flex_parent_data(wrapper: Callable[[str], str], widget: str) -> str:
    """Apply ``wrapper`` inside ``Expanded``/``Flexible`` when already present."""
    from figma_flutter_agent.generator.layout.flex_policy import hoist_flex_parent_data

    return hoist_flex_parent_data(wrapper, widget)


def _wrap_center_preserving_flex_parent_data(widget: str) -> str:
    """Center a flex child without nesting ``Expanded``/``Flexible`` under ``Center``."""
    return _hoist_flex_parent_data(lambda inner: f"Center(child: {inner})", widget)


def _wrap_sizing(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    from figma_flutter_agent.generator.layout.flex_policy import (
        apply_flex_wrap_to_widget,
    )

    if node.layout_slot is None:
        wrapped = apply_flex_wrap_to_widget(
            widget,
            parent_type=parent_type,
            node=node,
            parent_node=parent_node,
        )
    else:
        wrapped = widget
    sizing = node.sizing
    min_width, max_width = normalize_box_constraints(
        sizing.min_width,
        sizing.max_width,
    )
    min_height, max_height = normalize_box_constraints(
        sizing.min_height,
        sizing.max_height,
    )
    constraint_parts: list[str] = []
    if min_width is not None:
        constraint_parts.append(
            f"minWidth: {format_geometry_literal(min_width)}"
        )
    if max_width is not None:
        constraint_parts.append(
            f"maxWidth: {format_geometry_literal(max_width)}"
        )
    if min_height is not None:
        constraint_parts.append(
            f"minHeight: {format_geometry_literal(min_height)}"
        )
    if max_height is not None:
        constraint_parts.append(
            f"maxHeight: {format_geometry_literal(max_height)}"
        )
    if constraint_parts:
        wrapped = (
            f"ConstrainedBox(constraints: BoxConstraints({', '.join(constraint_parts)}), "
            f"child: {wrapped})"
        )
    # ROW cross-axis height pins run in ``post_flex_layout_slot_extents`` after
    # ``Expanded``/``Flexible`` wrappers — binding here duplicates ``OverflowBox``
    # layers and can emit ``maxHeight: double.infinity`` inside ``Expanded``.
    return wrapped


def _flex_spacing_field(node: CleanDesignTreeNode) -> str:
    """Emit Flutter 3.27+ ``spacing`` on ``Row``/``Column`` when Figma gap is set."""
    if node.spacing <= 0:
        return ""
    main = node.alignment.main or "start"
    if main in {"spaceBetween", "stretch"}:
        return ""
    gap = format_geometry_literal(node.spacing)
    return f"spacing: {gap}, "


_LIST_TILE_TRAIL_MAX_WIDTH = 32.0
_LIST_TILE_TRAILING_CHEVRON = (
    "Icon(Icons.chevron_right_rounded, "
    "color: Theme.of(context).colorScheme.onSurfaceVariant)"
)


def _button_list_tile_row_body(
    node: CleanDesignTreeNode, child_widgets: list[str]
) -> str:
    """Compose a settings-style ``Row`` for auto-layout list tile buttons."""
    parts: list[str] = []
    for index, (child_node, widget) in enumerate(
        zip(node.children, child_widgets, strict=True)
    ):
        if (
            index == len(node.children) - 1
            and len(node.children) >= 3
            and child_node.sizing.width is not None
            and float(child_node.sizing.width) <= _LIST_TILE_TRAIL_MAX_WIDTH
        ):
            widget = _LIST_TILE_TRAILING_CHEVRON
        if child_node.sizing.width_mode == SizingMode.FILL:
            parts.append(f"Expanded(child: {widget})")
        else:
            parts.append(widget)
    body = ", ".join(parts)
    return (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"{_flex_spacing_field(node)}"
        f"children: [{body}]"
        ")"
    )


def _stack_has_bottom_anchored_child(node: CleanDesignTreeNode) -> bool:
    """Return True when the stack pins chrome to the bottom edge (FID-21)."""
    for child in node.children:
        placement = child.stack_placement
        if placement is not None:
            if placement.vertical == "BOTTOM":
                return True
            if child.type == NodeType.BOTTOM_NAV and placement.bottom is not None:
                return True
    return False


def _should_pin_bottom(
    placement: StackPlacement,
    *,
    parent_height: float | None,
) -> bool:
    """Return True when a positioned child should use ``bottom:`` not ``top:``."""
    if placement.vertical == "BOTTOM":
        return True
    if (
        parent_height is not None
        and parent_height > 0
        and placement.top is not None
        and placement.height is not None
        and placement.height > 0
    ):
        return placement.top + placement.height >= parent_height - 2.0
    return False


def _resolved_bottom_offset(
    placement: StackPlacement,
    *,
    parent_height: float | None,
) -> float:
    """Resolve a bottom inset for bottom-anchored stack children."""
    if placement.bottom is not None and placement.bottom > 0:
        return float(placement.bottom)
    if (
        parent_height is not None
        and parent_height > 0
        and placement.top is not None
        and placement.height is not None
        and placement.height > 0
    ):
        return max(
            0.0, float(parent_height) - float(placement.top) - float(placement.height)
        )
    return 0.0


def _positioned_fields(
    placement: StackPlacement,
    *,
    render_boundary: bool = False,
    parent_height: float | None = None,
) -> list[str]:
    """Map Figma constraints to Positioned constructor fields.

    Flutter ``Positioned`` allows at most two of ``left``/``right``/``width`` (and
    ``top``/``bottom``/``height``). SCALE pins use explicit ``width``/``height`` when known.
    """

    def _g(value: float) -> str:
        if _snap_device_pixels_ctx.get():
            value = snap_to_device_pixel(value)
        return format_geometry_literal(value)

    fields: list[str] = []
    horizontal = placement.horizontal
    vertical = "TOP" if render_boundary else placement.vertical

    if horizontal == "LEFT":
        fields.append(f"left: {_g(placement.left)}")
        if placement.width is not None and placement.width > 0:
            fields.append(f"width: {_g(placement.width)}")
    elif horizontal == "RIGHT":
        fields.append(f"right: {_g(placement.right)}")
        if placement.width is not None and placement.width > 0:
            fields.append(f"width: {_g(placement.width)}")
    elif horizontal == "CENTER":
        fields.append(f"left: {_g(placement.left)}")
        if placement.width is not None and placement.width > 0:
            fields.append(f"width: {_g(placement.width)}")
    elif horizontal == "LEFT_RIGHT":
        fields.append(f"left: {_g(placement.left)}")
        fields.append(f"right: {_g(placement.right)}")
    elif horizontal == "SCALE":
        fields.append(f"left: {_g(placement.left)}")
        if placement.width is not None:
            fields.append(f"width: {_g(placement.width)}")
        else:
            fields.append(f"right: {_g(placement.right)}")

    if _should_pin_bottom(placement, parent_height=parent_height):
        fields.append(
            f"bottom: {_g(_resolved_bottom_offset(placement, parent_height=parent_height))}"
        )
        if placement.height is not None and placement.height > 0:
            fields.append(f"height: {_g(placement.height)}")
    elif vertical == "TOP":
        fields.append(f"top: {_g(placement.top)}")
        if placement.height is not None and placement.height > 0:
            fields.append(f"height: {_g(placement.height)}")
    elif vertical == "BOTTOM":
        fields.append(
            f"bottom: {_g(_resolved_bottom_offset(placement, parent_height=parent_height))}"
        )
        if placement.height is not None and placement.height > 0:
            fields.append(f"height: {_g(placement.height)}")
    elif vertical == "CENTER":
        fields.append(f"top: {_g(placement.top)}")
        if placement.height is not None and placement.height > 0:
            fields.append(f"height: {_g(placement.height)}")
    elif vertical == "TOP_BOTTOM":
        fields.append(f"top: {_g(placement.top)}")
        fields.append(f"bottom: {_g(placement.bottom)}")
    elif vertical == "SCALE":
        fields.append(f"top: {_g(placement.top)}")
        if placement.height is not None:
            fields.append(f"height: {_g(placement.height)}")
        else:
            fields.append(f"bottom: {_g(placement.bottom)}")

    if not fields:
        fields.extend([f"left: {_g(placement.left)}", f"top: {_g(placement.top)}"])
    return fields


def _positioned_fields_from_pins(
    pins: AxisPins,
    *,
    render_boundary: bool = False,
    parent_height: float | None = None,
) -> list[str]:
    """Map geometry-planner ``AxisPins`` to Positioned fields (T2 pin law)."""

    def _g(value: float) -> str:
        if _snap_device_pixels_ctx.get():
            value = snap_to_device_pixel(value)
        return format_geometry_literal(value)

    fields: list[str] = []
    free_h = pins.free_horizontal
    if free_h == "left" and pins.left is not None:
        fields.append(f"left: {_g(pins.left)}")
        if pins.width is not None and pins.width > 0:
            fields.append(f"width: {_g(pins.width)}")
    elif free_h == "right" and pins.right is not None:
        fields.append(f"right: {_g(pins.right)}")
        if pins.width is not None and pins.width > 0:
            fields.append(f"width: {_g(pins.width)}")
    elif free_h == "width":
        if pins.left is not None:
            fields.append(f"left: {_g(pins.left)}")
        if pins.width is not None:
            fields.append(f"width: {_g(pins.width)}")
        elif pins.right is not None:
            fields.append(f"right: {_g(pins.right)}")
    if pins.left is not None and not any(field.startswith("left:") for field in fields):
        fields.append(f"left: {_g(pins.left)}")

    free_v = pins.free_vertical
    if free_v == "top" and pins.top is not None:
        fields.append(f"top: {_g(pins.top)}")
        if pins.height is not None and pins.height > 0:
            fields.append(f"height: {_g(pins.height)}")
    elif free_v == "bottom" and pins.bottom is not None:
        fields.append(f"bottom: {_g(pins.bottom)}")
        if pins.height is not None and pins.height > 0:
            fields.append(f"height: {_g(pins.height)}")
    elif free_v == "height":
        if pins.top is not None:
            fields.append(f"top: {_g(pins.top)}")
        if pins.height is not None:
            fields.append(f"height: {_g(pins.height)}")
        elif pins.bottom is not None:
            fields.append(f"bottom: {_g(pins.bottom)}")
    if pins.top is not None and not any(field.startswith("top:") for field in fields):
        fields.append(f"top: {_g(pins.top)}")

    if not fields:
        if pins.left is not None:
            fields.append(f"left: {_g(pins.left)}")
        if pins.top is not None:
            fields.append(f"top: {_g(pins.top)}")
    _ = parent_height
    return fields


def _apply_layout_slot_wraps(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None = None,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Apply planner-authorized wrappers (flex, T3 delta_top, T5 RepaintBoundary)."""
    slot = node.layout_slot
    if slot is None:
        return widget
    flex_parent_child = parent_type in {NodeType.ROW, NodeType.COLUMN}
    working = widget
    if WrapKind.CONSTRAINED_BOX in slot.wraps:
        from figma_flutter_agent.generator.layout.responsive import (
            current_responsive_emit,
            responsive_host_width_literal,
        )

        width = node.sizing.width
        width_lit = responsive_host_width_literal(
            width,
            width_mode=node.sizing.width_mode,
        )
        ctx = current_responsive_emit()
        skip_redundant = (
            width_lit == "double.infinity"
            and ctx.enabled
            and WrapKind.CROSS_STRETCH_WIDTH in slot.wraps
        )
        if not skip_redundant:
            from figma_flutter_agent.generator.layout.flex_policy import (
                flex_host_prefers_min_height_pin,
            )

            height = node.sizing.height
            if (
                parent_type == NodeType.ROW
                and height is not None
                and height > 0
                and node.sizing.height_mode in {SizingMode.FIXED, SizingMode.FILL}
            ):
                height_lit = format_geometry_literal(height)
                if flex_host_prefers_min_height_pin(node):
                    working = (
                        f"ConstrainedBox("
                        f"constraints: BoxConstraints(minHeight: {height_lit}), "
                        f"child: {working})"
                    )
                else:
                    working = (
                        f"SizedBox(width: {width_lit}, "
                        f"height: {height_lit}, "
                        f"child: {working})"
                    )
            else:
                working = f"SizedBox(width: {width_lit}, child: {working})"
    if WrapKind.DELTA_TOP_PADDING in slot.wraps:
        from figma_flutter_agent.generator.layout.flex_policy import (
            text_host_is_tight_positioned,
        )

        metrics = node.text_metrics_frame
        if (
            metrics is not None
            and metrics.delta_top is not None
            and not text_host_is_tight_positioned(node)
        ):
            top_lit = format_geometry_literal(metrics.delta_top)
            working = (
                f"Padding(padding: EdgeInsets.only(top: {top_lit}), child: {working})"
            )
    if WrapKind.REPAINT_BOUNDARY in slot.wraps:
        working = wrap_repaint_boundary(working)
    if slot.min_height is not None or slot.max_height is not None:
        min_height, max_height = normalize_box_constraints(
            slot.min_height,
            slot.max_height,
        )
        min_lit = (
            format_geometry_literal(min_height)
            if min_height is not None
            else "0.0"
        )
        max_lit = (
            format_geometry_literal(max_height)
            if max_height is not None
            else "double.infinity"
        )
        working = (
            f"ConstrainedBox("
            f"constraints: BoxConstraints(minHeight: {min_lit}, maxHeight: {max_lit}), "
            f"child: {working})"
        )
    # ``Expanded`` / ``Flexible`` must be direct ``Row``/``Column`` children — apply last.
    if flex_parent_child:
        if WrapKind.EXPANDED in slot.wraps:
            working = f"Expanded(child: {working})"
        elif WrapKind.FLEXIBLE_LOOSE in slot.wraps:
            from figma_flutter_agent.generator.layout.flex_policy import emit_flexible_loose

            working = emit_flexible_loose(working)
        elif WrapKind.CROSS_STRETCH_WIDTH in slot.wraps and not _is_stretched_width_box(
            working
        ):
            working = f"SizedBox(width: double.infinity, child: {working})"
        elif WrapKind.CROSS_STRETCH_HEIGHT in slot.wraps:
            from figma_flutter_agent.generator.layout.flex_policy import (
                bind_row_cross_axis_height,
            )

            working = bind_row_cross_axis_height(node, working, parent_row=parent_node)
    return working


def _is_stretched_width_box(widget: str) -> bool:
    return widget.lstrip().startswith("SizedBox(width: double.infinity, child:")


def _node_layout_size(
    node: CleanDesignTreeNode,
    placement: StackPlacement | None,
) -> tuple[float | None, float | None]:
    """Resolve Figma frame size for bounded Stack / Positioned codegen."""
    width = node.sizing.width
    height = node.sizing.height
    if placement is not None:
        if placement.width is not None and placement.width > 0:
            width = placement.width
        if placement.height is not None and placement.height > 0:
            height = placement.height
    return width, height


def figma_positioned_dimensions(
    node: CleanDesignTreeNode,
    placement: StackPlacement | None = None,
) -> tuple[float | None, float | None]:
    """Return explicit Figma width/height to pin on a ``Positioned`` child, if any."""
    placement = placement or node.stack_placement
    if placement is None:
        return None, None
    width, height = _node_layout_size(node, placement)
    return (
        width if width is not None and width > 0 else None,
        height if height is not None and height > 0 else None,
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
    width, height = figma_positioned_dimensions(node, placement)
    left = placement.left if placement.left is not None else node.offset_x
    top = placement.top if placement.top is not None else node.offset_y
    pin_bottom = _should_pin_bottom(placement, parent_height=parent_height) or any(
        field.startswith("bottom:") for field in fields
    )
    if (
        left is not None
        and top is not None
        and width is not None
        and height is not None
    ):
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
            elif horizontal == "LEFT_RIGHT":
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
                "Alignment.topLeft"
                if is_mobile_artboard_width(width)
                else "Alignment.topCenter"
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
        )
        return wrap_artboard_preview_layout_builder(
            preview_child=preview_child,
            fallback=fallback,
        )
    artboard = (
        f"SizedBox(width: {width_token}, height: {height_token}, child: {stack_widget})"
    )
    if responsive_enabled:
        if is_mobile_artboard_width(width):
            scroll_body = f"SingleChildScrollView(child: {stack_widget})"
            fallback = (
                "LayoutBuilder("
                "builder: (context, constraints) {"
                "return Align("
                "alignment: Alignment.topCenter, "
                "child: SizedBox("
                "width: constraints.maxWidth, "
                f"child: {scroll_body}"
                "),"
                ");"
                "},"
                ")"
            )
        else:
            viewport_align = "Alignment.topCenter"
            fitted = (
                "Align("
                f"alignment: {viewport_align}, "
                "child: FittedBox("
                "fit: BoxFit.scaleDown, "
                f"alignment: {viewport_align}, "
                f"child: {artboard},"
                "),"
                ")"
            )
            fallback = fitted
        preview_child = artboard_preview_sized_box(
            child=stack_widget,
            alignment=(
                "Alignment.topLeft"
                if is_mobile_artboard_width(width)
                else "Alignment.topCenter"
            ),
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
    if responsive_enabled and is_mobile_artboard_width(width):
        artboard_width = "constraints.maxWidth"
        fallback = live_scroll_column_viewport(
            artboard_width_expr=artboard_width,
            column_widget=column_widget,
        )
    else:
        artboard_width = (
            f"constraints.maxWidth < {width_token} ? constraints.maxWidth : {width_token}"
        )
        artboard = (
            f"SizedBox(width: {artboard_width}, height: {height_token}, "
            f"child: {column_widget})"
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


def _flex_input_content_padding(
    node: CleanDesignTreeNode,
    hint_node: CleanDesignTreeNode | None,
    field_height: float | None,
) -> str | None:
    """Derive ``InputDecoration.contentPadding`` for flex-hug ``INPUT`` frames."""
    if field_height is None or field_height <= 0:
        return None
    pad = node.padding
    left = pad.left if pad is not None and pad.left is not None else 16.0
    right = pad.right if pad is not None and pad.right is not None else 16.0
    if pad is not None and ((pad.top or 0) > 0 or (pad.bottom or 0) > 0):
        top = pad.top or 0.0
        bottom = pad.bottom or 0.0
        return (
            f"contentPadding: EdgeInsets.fromLTRB(" f"{left}, {top}, {right}, {bottom})"
        )
    font_size = hint_node.style.font_size if hint_node is not None else 14.0
    text_height = (
        hint_node.style.glyph_height
        if hint_node is not None and hint_node.style.glyph_height
        else font_size
    )
    top = max(0.0, (float(field_height) - float(text_height)) / 2.0)
    bottom = max(0.0, float(field_height) - top - float(text_height))
    return f"contentPadding: EdgeInsets.fromLTRB({left}, {top}, {right}, {bottom})"


def _input_content_padding(
    surface: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    field_height: float | None,
) -> str | None:
    """Derive ``InputDecoration.contentPadding`` from Figma placeholder placement."""
    if (
        surface is None
        or hint_node is None
        or field_height is None
        or field_height <= 0
    ):
        return None
    placement = hint_node.stack_placement
    if placement is None:
        return None
    left = placement.left if placement.left is not None else 20.0
    text_height = hint_node.style.glyph_height or placement.height
    font_size = hint_node.style.font_size or 16.0
    line_height = hint_node.style.line_height or 1.0
    computed_height = font_size * line_height
    if text_height is None or text_height <= 0:
        text_height = computed_height
    figma_top = (placement.top if placement.top is not None else 0.0) + (
        hint_node.style.glyph_top_offset or 0.0
    )
    centered_top = max(0.0, (field_height - text_height) / 2.0)
    top = figma_top if figma_top >= centered_top - 1.0 else centered_top
    bottom = max(0.0, field_height - top - text_height)
    right = left
    return f"contentPadding: EdgeInsets.fromLTRB({left}, {top}, {right}, {bottom})"


def _planner_input_content_padding(node: CleanDesignTreeNode) -> str | None:
    """Use geometry-planner INPUT padding channel when present."""
    metrics = node.text_metrics_frame
    if metrics is None or metrics.input_padding_top is None:
        return None
    pad = node.padding
    left = pad.left if pad is not None and pad.left is not None else 16.0
    right = pad.right if pad is not None and pad.right is not None else left
    top = format_geometry_literal(metrics.input_padding_top)
    bottom = format_geometry_literal(metrics.input_padding_bottom or 0.0)
    left_lit = format_geometry_literal(left)
    right_lit = format_geometry_literal(right)
    return f"contentPadding: EdgeInsets.fromLTRB({left_lit}, {top}, {right_lit}, {bottom})"


def _stack_input_decoration(
    surface: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    hint: str,
    *,
    host_node: CleanDesignTreeNode | None = None,
    field_height: float | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    surface_on_container: bool = False,
    suffix_icon: str | None = None,
) -> str:
    """Build ``InputDecoration`` for heuristic input stacks."""
    hint_text = escape_dart_string(hint)
    fields = [f"hintText: '{hint_text}'"]
    if hint_node is not None:
        fields.append(
            f"hintStyle: {text_style_expr(hint_node, bundled_font_families=bundled_font_families, dart_weight_overrides_by_family=dart_weight_overrides_by_family, text_theme_slot_by_style_name=text_theme_slot_by_style_name, text_theme_size_slots=text_theme_size_slots)}"
        )
    if surface_on_container:
        padding = None
        if host_node is not None and host_node.layout_slot is not None:
            padding = _planner_input_content_padding(host_node)
        if padding is None:
            padding = _input_content_padding(surface, hint_node, field_height)
        if padding is None and host_node is not None:
            padding = _flex_input_content_padding(host_node, hint_node, field_height)
        if padding is not None:
            fields.append(padding)
        else:
            left = 20.0
            if (
                hint_node is not None
                and hint_node.stack_placement is not None
                and hint_node.stack_placement.left is not None
            ):
                left = hint_node.stack_placement.left
            fields.append(
                f"contentPadding: EdgeInsets.symmetric(horizontal: {left}, vertical: 0)"
            )
        fields.append("border: InputBorder.none")
        fields.append("enabledBorder: InputBorder.none")
        fields.append("focusedBorder: InputBorder.none")
        fields.append("disabledBorder: InputBorder.none")
        fields.append("errorBorder: InputBorder.none")
        fields.append("focusedErrorBorder: InputBorder.none")
    else:
        padding = _input_content_padding(surface, hint_node, field_height)
        if padding is not None:
            fields.append(padding)
        if surface is not None and surface.style.background_color:
            fields.append("filled: true")
            fields.append(f"fillColor: {dart_color_expr(surface.style)}")
        radius = surface.style.border_radius if surface is not None else None
        if radius is not None:
            fields.append(
                "border: OutlineInputBorder("
                f"borderRadius: BorderRadius.circular({radius}), "
                "borderSide: BorderSide.none"
                ")"
            )
            fields.append(
                "enabledBorder: OutlineInputBorder("
                f"borderRadius: BorderRadius.circular({radius}), "
                "borderSide: BorderSide.none"
                ")"
            )
    if suffix_icon is not None:
        fields.append(f"suffixIcon: {suffix_icon}")
    return f"InputDecoration({', '.join(fields)})"


def _render_stack_input(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    embed_in_trailing_row: bool = False,
) -> str:
    """Render a positioned ``TextField`` for classic absolute input groups."""
    surface = input_surface_node(node) or interaction_surface_node(node)
    hint_node = input_hint_node(node)
    hint = input_hint_text(node)
    width, height = _node_layout_size(surface or node, node.stack_placement)
    field_height = surface.sizing.height if surface is not None else height
    decoration = _stack_input_decoration(
        surface,
        hint_node,
        hint,
        host_node=node,
        field_height=field_height,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        surface_on_container=surface is not None
        and surface.style.background_color is not None,
    )
    obscure = (
        "true"
        if looks_like_password_field_stack(node) or "password" in hint.lower()
        else "false"
    )
    input_style = (
        text_style_expr(
            hint_node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if hint_node is not None
        else "Theme.of(context).textTheme.bodyMedium"
    )
    value_text = input_flex_value_text(node)
    if value_text:
        escaped_value = escape_dart_string(value_text)
        vertical_align = (
            "textAlignVertical: TextAlignVertical.center, "
            if field_height is not None and field_height > 0
            else ""
        )
        field = (
            f"TextField("
            f"controller: TextEditingController(text: '{escaped_value}'), "
            f"obscureText: {obscure}, "
            f"{vertical_align}"
            f"style: {input_style}, decoration: {decoration})"
        )
    else:
        field = f"TextField(obscureText: {obscure}, style: {input_style}, decoration: {decoration})"
    if not embed_in_trailing_row:
        box_decoration = (
            box_decoration_expr(
                surface.style,
                width=surface.sizing.width,
                height=surface.sizing.height,
            )
            if surface is not None
            else None
        )
        if (
            box_decoration is not None
            and width is not None
            and width > 0
            and height is not None
            and height > 0
        ):
            field = (
                f"Container("
                f"width: {width}, height: {height}, "
                f"decoration: {box_decoration}, "
                f"child: {field}"
                f")"
            )
        elif width is not None and width > 0 and height is not None and height > 0:
            field = f"SizedBox(width: {width}, height: {height}, child: {field})"
        elif width is not None and width > 0:
            field = f"SizedBox(width: {width}, child: {field})"
    elif height is not None and height > 0:
        field = f"SizedBox(height: {height}, child: {field})"
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    label = escape_dart_string(node.accessibility_label or hint)
    field = f"Semantics(label: '{label}', child: {field})"
    return _finalize_widget(node, field, parent_type=parent_type)


def _render_stroke_glyph_fallback(node: CleanDesignTreeNode) -> str | None:
    """Material icon fallback for vectors missing exported SVG assets."""
    if node.type != NodeType.VECTOR or node.vector_asset_key:
        return None
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    if width <= 0 or height <= 0:
        return None
    has_stroke = node.style.has_stroke
    has_fill = bool(node.style.background_color)
    if not has_stroke and not has_fill:
        return None
    color = dart_color_expr(
        node.style,
        css_key="border-color" if has_stroke else "background-color",
        fallback="0xFF52525C",
    )
    if has_stroke and height >= width * 1.15 and width <= 14.0:
        # Figma reports tight vector bounds (e.g. 5×10); scale for ~48dp tap targets.
        chevron_size = min(max(width, height) * 2.4, 24.0)
        chevron_size = max(chevron_size, 18.0)
        return (
            f"Icon(Icons.chevron_left, color: {color}, "
            f"size: {format_geometry_literal(chevron_size)})"
        )
    size = max(width, height, 12.0)
    if 9.0 <= width <= 22.0 and 9.0 <= height <= 22.0:
        return f"Icon(Icons.calendar_today_outlined, color: {color}, size: {size})"
    return None


_FROSTED_FILL_OPACITY = 0.72


def _effective_backdrop_blur(node: CleanDesignTreeNode) -> float | None:
    """Resolve frosted-glass blur radius (``BACKGROUND_BLUR`` or legacy ``layerBlur`` on hosts)."""
    if node.style.background_blur is not None and node.style.background_blur > 0:
        return node.style.background_blur
    if (
        node.type in {NodeType.COLUMN, NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}
        and node.style.layer_blur is not None
        and node.style.layer_blur > 0
    ):
        return node.style.layer_blur
    return None


def _effective_content_blur(node: CleanDesignTreeNode) -> float | None:
    """Resolve content blur for leaf/media nodes (``LAYER_BLUR`` without backdrop host)."""
    if node.style.layer_blur is None or node.style.layer_blur <= 0:
        return None
    if (
        _effective_backdrop_blur(node) is not None
        and node.style.background_blur is None
        and node.type
        in {NodeType.COLUMN, NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}
    ):
        return None
    if node.type in {NodeType.VECTOR, NodeType.IMAGE}:
        return None
    if node.type in {NodeType.TEXT, NodeType.CONTAINER}:
        return node.style.layer_blur
    return None


def _wrap_content_layer_blur(node: CleanDesignTreeNode, widget: str) -> str:
    """Apply ``ImageFiltered`` for content ``LAYER_BLUR`` (FID-41)."""
    blur = _effective_content_blur(node)
    if blur is None:
        return widget
    sigma = format_figma_blur_sigma_literal(blur)
    return (
        f"ImageFiltered("
        f"imageFilter: ImageFilter.blur(sigmaX: {sigma}, sigmaY: {sigma}), "
        f"child: {widget})"
    )


def _drop_shadow_exprs(style: NodeStyle) -> str | None:
    """Comma-separated ``BoxShadow`` list for drop effects on a node."""
    if not style.effects:
        return None
    shadows = ", ".join(
        _shadow_expr(effect)
        for effect in style.effects
        if effect.kind == "drop"
    )
    return shadows or None


def _wrap_frosted_layer_blur(node: CleanDesignTreeNode, widget: str) -> str:
    """Apply Figma frosted glass via ``BackdropFilter`` (FID-06 / FID-41)."""
    blur = _effective_backdrop_blur(node)
    if blur is None or blur <= 0:
        return widget
    sigma = format_figma_blur_sigma_literal(blur)
    if node.style.border_radius_corners is not None:
        clip_open = f"ClipRRect(borderRadius: {border_radius_expr(node.style)}, child: "
    elif node.style.border_radius is not None:
        clip_open = (
            f"ClipRRect(borderRadius: BorderRadius.circular({node.style.border_radius}), "
            f"child: "
        )
    else:
        clip_open = "ClipRect(child: "
    fill_color = (
        dart_color_expr(node.style)
        if node.style.background_color
        else "const Color(0xFFFFFFFF)"
    )
    frosted = (
        f"{clip_open}"
        f"BackdropFilter("
        f"filter: ImageFilter.blur(sigmaX: {sigma}, sigmaY: {sigma}), "
        f"child: Container("
        f"decoration: BoxDecoration("
        f"color: {fill_color}.withOpacity({_FROSTED_FILL_OPACITY})"
        f"), child: {widget}))"
        f")"
    )
    drop_shadows = _drop_shadow_exprs(node.style)
    if drop_shadows is None:
        return frosted
    return (
        "DecoratedBox("
        f"decoration: BoxDecoration(boxShadow: [{drop_shadows}]), "
        f"child: {frosted}"
        ")"
    )


def _is_form_field_group_column(node: CleanDesignTreeNode) -> bool:
    """Return True for label + field stacks that must grow past a Figma bbox height."""
    if node.type != NodeType.COLUMN:
        return False
    child_types = {child.type for child in node.children}
    if NodeType.TEXT in child_types and NodeType.INPUT in child_types:
        return True
    if NodeType.TEXT in child_types and len(node.children) > 1:
        return any(
            child.type
            in {NodeType.INPUT, NodeType.BUTTON, NodeType.COLUMN, NodeType.ROW}
            for child in node.children
        )
    return False


def _text_has_multiple_lines(node: CleanDesignTreeNode) -> bool:
    """Return True when Figma text content spans more than one line."""
    if node.type != NodeType.TEXT:
        return False
    raw = (node.text or "").strip()
    if not raw:
        return False
    return "\n" in raw or len(raw.splitlines()) > 1


def _row_hosts_stacked_column_peer(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` pairs a fixed bbox with a multi-child ``Column`` peer."""
    if node.type != NodeType.ROW:
        return False
    return any(
        child.type == NodeType.COLUMN and len(child.children) >= 2
        for child in node.children
    )


def _flex_child_should_bind_fixed_height(node: CleanDesignTreeNode) -> bool:
    """Return True when a COLUMN width-fill child may also pin Figma frame height."""
    from figma_flutter_agent.generator.layout.flex_policy import (
        flex_host_prefers_min_height_pin,
    )

    height = node.sizing.height
    if height is None or height <= 0:
        return False
    if flex_host_prefers_min_height_pin(node):
        return False
    if node.type == NodeType.BUTTON:
        from figma_flutter_agent.parser.interaction import (
            button_has_composite_row_body,
            button_has_list_tile_row_body,
        )

        if button_has_composite_row_body(node) or button_has_list_tile_row_body(node):
            return False
    if node.sizing.height_mode == SizingMode.FILL:
        return True
    if node.type == NodeType.ROW and _row_hosts_stacked_column_peer(node):
        return False
    if _is_form_field_group_column(node):
        return False
    if node.type == NodeType.COLUMN and len(node.children) > 1:
        return False
    if node.type == NodeType.TEXT and _text_has_multiple_lines(node):
        return False
    if (
        node.type == NodeType.COLUMN
        and len(node.children) == 1
        and not _flex_child_should_bind_fixed_height(node.children[0])
    ):
        return False
    if node.type == NodeType.CONTAINER and len(node.children) == 1:
        return _flex_child_should_bind_fixed_height(node.children[0])
    return True


def _wrap_widget_with_box_decoration(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    responsive_enabled: bool = False,
    design_artboard_width: float | None = None,
) -> str:
    """Wrap flex hosts with Figma padding and frame fill/radius."""

    def _decorate(inner: str) -> str:
        return _decorate_widget_with_box_decoration(
            node,
            inner,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
        )

    return _hoist_flex_parent_data(_decorate, widget)


def _decorate_widget_with_box_decoration(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    responsive_enabled: bool = False,
    design_artboard_width: float | None = None,
) -> str:
    """Apply padding and painted bounds to a non-flex host expression."""
    from figma_flutter_agent.generator.layout.responsive import responsive_emit_width

    widget = wrap_flex_auto_layout_padding(node, widget)
    if looks_like_bottom_docked_sheet(node):
        fields: list[str] = []
        if node.style.background_color:
            fields.append(f"color: {dart_color_expr(node.style)}")
        if node.style.effects and _effective_backdrop_blur(node) is None:
            shadows = ", ".join(
                _shadow_expr(effect)
                for effect in node.style.effects
                if effect.kind == "drop"
            )
            if shadows:
                fields.append(f"boxShadow: [{shadows}]")
        radius = node.style.border_radius or 28.0
        fields.append(
            "borderRadius: BorderRadius.only("
            f"topLeft: Radius.circular({radius}), "
            f"topRight: Radius.circular({radius})"
            ")"
        )
        decoration = f"BoxDecoration({', '.join(fields)})"
    else:
        decoration = box_decoration_expr(
            node.style,
            width=node.sizing.width,
            height=node.sizing.height,
            omit_shadows=_effective_backdrop_blur(node) is not None,
        )
    if decoration is None:
        return widget
    from figma_flutter_agent.generator.layout.flex_policy import (
        row_is_status_pill_badge,
        row_is_tight_horizontal_pill_label,
    )

    width, height = _node_layout_size(node, node.stack_placement)
    if not _flex_child_should_bind_fixed_height(node):
        height = None
    if node.sizing.width_mode == SizingMode.FILL:
        width = None
    if row_is_tight_horizontal_pill_label(node) or row_is_status_pill_badge(node):
        width = None
    if responsive_enabled:
        width = responsive_emit_width(width)

    foreground = box_foreground_decoration_expr(node.style)
    if width is not None and width > 0 and height is not None and height > 0:
        if foreground is not None:
            wrapped = (
                f"Container(width: {width}, height: {height}, decoration: {decoration}, "
                f"foregroundDecoration: {foreground}, child: {widget})"
            )
        else:
            wrapped = (
                f"Container(width: {width}, height: {height}, decoration: {decoration}, "
                f"child: {widget})"
            )
    elif width is not None and width > 0:
        if foreground is not None:
            wrapped = (
                f"Container(width: {width}, decoration: {decoration}, "
                f"foregroundDecoration: {foreground}, child: {widget})"
            )
        else:
            wrapped = (
                f"Container(width: {width}, decoration: {decoration}, "
                f"child: {widget})"
            )
    elif height is not None and height > 0:
        if foreground is not None:
            wrapped = (
                f"Container(height: {height}, decoration: {decoration}, "
                f"foregroundDecoration: {foreground}, child: {widget})"
            )
        else:
            wrapped = (
                f"Container(height: {height}, decoration: {decoration}, "
                f"child: {widget})"
            )
    elif foreground is not None:
        wrapped = (
            f"Container(decoration: {decoration}, foregroundDecoration: {foreground}, "
            f"child: {widget})"
        )
    else:
        wrapped = f"Container(decoration: {decoration}, child: {widget})"
    if _effective_backdrop_blur(node) is not None:
        return _wrap_frosted_layer_blur(node, wrapped)
    return wrapped


def _find_icon_glyph_expr(node: CleanDesignTreeNode) -> str | None:
    """Resolve a Material icon fallback for vector chrome under a tap target."""
    from figma_flutter_agent.parser.interaction import stroke_plus_icon_expr

    plus = stroke_plus_icon_expr(node)
    if plus is not None:
        return plus
    fallback = _render_stroke_glyph_fallback(node)
    if fallback is not None:
        return fallback
    for child in node.children:
        found = _find_icon_glyph_expr(child)
        if found is not None:
            return found
    return None


def _find_trailing_input_icon_expr(node: CleanDesignTreeNode) -> str | None:
    """Resolve a stroke/icon fallback for compact INPUT trailing chrome."""
    return _find_icon_glyph_expr(node)


def _render_input_trailing_suffix_icon(
    chrome: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Compact ``InputDecoration.suffixIcon`` for calendar/chevron chrome."""
    del uses_svg, theme_variant, bundled_font_families, dart_weight_overrides_by_family
    del text_theme_slot_by_style_name, text_theme_size_slots
    from figma_flutter_agent.generator.layout.cupertino import _on_pressed_handler

    icon_expr = _find_trailing_input_icon_expr(chrome) or (
        "Icon(Icons.calendar_today_outlined, size: 18.0)"
    )
    on_pressed = _on_pressed_handler(chrome.id, "button-action")
    return (
        "IconButton("
        f"icon: {icon_expr}, "
        "padding: EdgeInsets.zero, "
        "visualDensity: VisualDensity.compact, "
        "constraints: const BoxConstraints(minWidth: 32, minHeight: 32), "
        f"{on_pressed}"
        ")"
    )


def _render_flex_input_with_trailing_chrome(
    node: CleanDesignTreeNode,
    trailing: list[CleanDesignTreeNode],
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    uses_svg: bool,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """``TextField`` with trailing calendar/chevron chrome inside the same fill."""
    suffix_icon = _render_input_trailing_suffix_icon(
        trailing[0],
        uses_svg=uses_svg,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    surface = input_surface_node(node)
    hint_node = input_hint_node(node)
    hint = input_hint_text(node)
    width, height = _node_layout_size(surface or node, node.stack_placement)
    field_height = surface.sizing.height if surface is not None else height
    decoration = _stack_input_decoration(
        surface,
        hint_node,
        hint,
        host_node=node,
        field_height=field_height,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        surface_on_container=surface is not None
        and surface.style.background_color is not None,
        suffix_icon=suffix_icon,
    )
    obscure = (
        "true"
        if looks_like_password_field_stack(node) or "password" in hint.lower()
        else "false"
    )
    input_style = (
        text_style_expr(
            hint_node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if hint_node is not None
        else "Theme.of(context).textTheme.bodyMedium"
    )
    value_text = input_flex_value_text(node)
    vertical_align = (
        "textAlignVertical: TextAlignVertical.center, "
        if field_height is not None and field_height > 0
        else ""
    )
    if value_text:
        escaped_value = escape_dart_string(value_text)
        field = (
            f"TextField("
            f"controller: TextEditingController(text: '{escaped_value}'), "
            f"obscureText: {obscure}, "
            f"{vertical_align}"
            f"style: {input_style}, decoration: {decoration})"
        )
    else:
        field = f"TextField(obscureText: {obscure}, style: {input_style}, decoration: {decoration})"
    if height is not None and height > 0:
        field = f"SizedBox(height: {height}, child: {field})"
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    box_decoration = (
        box_decoration_expr(
            surface.style,
            width=surface.sizing.width,
            height=surface.sizing.height,
        )
        if surface is not None
        else None
    )
    if (
        box_decoration is not None
        and width is not None
        and width > 0
        and height is not None
        and height > 0
    ):
        composed = (
            f"Container(width: {width}, height: {height}, "
            f"decoration: {box_decoration}, child: {field})"
        )
    else:
        composed = field
    label = escape_dart_string(node.accessibility_label or input_hint_text(node))
    return _finalize_widget(
        node,
        f"Semantics(label: '{label}', child: {composed})",
        parent_type=parent_type,
    )


def _should_omit_positioned_height(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """Let stack/flex hosts grow past fractional Figma frame heights when needed."""
    from figma_flutter_agent.generator.layout.flex_policy import (
        stack_metadata_timestamp_host,
    )

    from figma_flutter_agent.generator.layout.flex_policy import (
        column_bounded_slot_should_grow,
    )

    if column_bounded_slot_should_grow(node):
        return True
    if stack_metadata_timestamp_host(node, parent_node=parent_node):
        return True
    if node.type != NodeType.TEXT:
        return False
    placement = node.stack_placement
    if placement is None or placement.height is None or placement.height <= 0:
        return False
    text = node.text or ""
    if "\n" in text:
        return True
    font_size = node.style.font_size
    glyph_height = node.style.glyph_height
    if font_size is not None and glyph_height is not None:
        return glyph_height > font_size * 1.45
    if font_size is not None and font_size > 0:
        line_factor = node.style.line_height if node.style.line_height else 1.2
        if float(placement.height) >= font_size * line_factor * 1.35:
            return True
    return False


def _stack_child_left(child: CleanDesignTreeNode) -> float:
    if child.stack_placement is not None and child.stack_placement.left is not None:
        return float(child.stack_placement.left)
    return float(child.offset_x)


def _is_logo_wordmark_stack(node: CleanDesignTreeNode) -> bool:
    if node.type != NodeType.STACK or len(node.children) != 3:
        return False
    texts = [child for child in node.children if child.type == NodeType.TEXT]
    if len(texts) != 2:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if node.stack_placement is not None:
        if node.stack_placement.width is not None:
            width = node.stack_placement.width
        if node.stack_placement.height is not None:
            height = node.stack_placement.height
    return (
        width is not None and height is not None and width <= 220.0 and height <= 48.0
    )


def _logo_wordmark_stack_size(node: CleanDesignTreeNode) -> tuple[float, float]:
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    if node.stack_placement is not None:
        if node.stack_placement.width is not None:
            width = float(node.stack_placement.width)
        if node.stack_placement.height is not None:
            height = float(node.stack_placement.height)
    return width, height


def _render_logo_wordmark_stack(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str,
    cluster_classes: dict[str, str] | None,
    cluster_vector_variants: dict[str, ClusterVectorVariant] | None,
    cluster_vector_variant: ClusterVectorVariant | None,
    skip_cluster_id: str | None,
    responsive_enabled: bool,
    design_artboard_width: float | None = None,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    width, height = _logo_wordmark_stack_size(node)
    child_widgets = [
        render_node_body(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
            parent_node=node,
            theme_variant=theme_variant,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
            cluster_vector_variant=cluster_vector_variant,
            skip_cluster_id=skip_cluster_id,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        for child in sorted(node.children, key=_stack_child_left)
    ]
    return (
        f"SizedBox("
        f"width: {format_geometry_literal(width)}, "
        f"height: {format_geometry_literal(height)}, "
        f"child: Stack(clipBehavior: Clip.none, children: [{', '.join(child_widgets)}])"
        ")"
    )


def _render_explicit_multiline_text_lines(
    node: CleanDesignTreeNode,
    *,
    style_expr: str,
    text_align_suffix: str,
) -> str | None:
    """Preserve Figma hard line breaks in one ``Text`` without ``maxLines: 1`` clipping."""
    if node.text_spans:
        return None
    raw = (node.text or "").strip()
    if "\n" not in raw:
        return None
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if len(lines) < 2:
        return None
    trailing = text_widget_trailing_params(
        node.style,
        text_align_suffix=text_align_suffix,
        soft_wrap=True,
    )
    text = escape_dart_string(raw)
    return f"Text('{text}', style: {style_expr}, {trailing})"


def _wrap_bounded_positioned_slot_child(
    widget: str,
    *,
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Clip slot overflow without ``RenderFlex`` layout assertions.

    ``ClipRect`` alone only affects painting. When a ``Column`` with
    ``mainAxisSize: min`` is fractionally taller than its ``Positioned`` slot
    (text metrics rounding, flex ``spacing``), Flutter still throws overflow.
    ``OverflowBox`` loosens the flex axis while the outer ``Positioned`` slot
    keeps the painted bounds stable.
    """
    from figma_flutter_agent.generator.layout.flex_policy import (
        column_bounded_slot_needs_vertical_scroll,
        column_bounded_slot_should_grow,
        stack_metadata_timestamp_host,
    )

    if stack_metadata_timestamp_host(node, parent_node=parent_node):
        return widget

    if column_bounded_slot_should_grow(node):
        return widget

    if column_bounded_slot_needs_vertical_scroll(node):
        scroll_body = f"SingleChildScrollView(child: {widget})"
        if child_has_outward_paint(node):
            return scroll_body
        return f"ClipRect(child: {scroll_body})"

    placement = node.stack_placement
    width, height = _node_layout_size(node, placement)
    if node.type == NodeType.ROW:
        align = "Alignment.centerLeft"
        if width is not None and width > 0:
            loosen = f"maxWidth: {format_geometry_literal(width)}, "
        else:
            loosen = "maxWidth: double.infinity, "
    else:
        align = "Alignment.topCenter"
        if height is not None and height > 0:
            loosen = f"maxHeight: {format_geometry_literal(height)}, "
        else:
            loosen = "maxHeight: double.infinity, "
    inner = (
        f"Align(alignment: {align}, child: OverflowBox("
        f"alignment: {align}, {loosen}"
        f"child: {widget}))"
    )
    if child_has_outward_paint(node):
        return inner
    return f"ClipRect(child: {inner})"


def _apply_stack_position(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None = None,
    fill_parent: bool = False,
    scroll_content_root: bool = False,
) -> str:
    if scroll_content_root:
        return widget
    if parent_type not in {NodeType.STACK, NodeType.BUTTON}:
        return widget
    if (
        parent_node is not None
        and parent_node.type == NodeType.STACK
    ):
        from figma_flutter_agent.generator.layout.flex_policy import (
            stack_should_flow_as_column,
        )

        if stack_should_flow_as_column(parent_node):
            return widget
    if fill_parent:
        return f"Positioned.fill(child: {widget})"
    placement = node.stack_placement
    if placement is None and node.layout_positioning == "ABSOLUTE":
        placement = StackPlacement(left=node.offset_x, top=node.offset_y)
    if placement is None:
        return widget
    if parent_node is not None and parent_node.type == NodeType.STACK:
        parent_width = parent_node.sizing.width
        if parent_width is None and parent_node.stack_placement is not None:
            parent_width = parent_node.stack_placement.width
        if parent_width is not None and parent_width > 0:
            from figma_flutter_agent.parser.layout import (
                clamp_stack_child_placement_to_parent,
            )

            placement = clamp_stack_child_placement_to_parent(
                placement,
                float(parent_width),
            )
    parent_height: float | None = None
    if parent_node is not None:
        parent_height = parent_node.sizing.height
        if parent_height is None and parent_node.stack_placement is not None:
            parent_height = parent_node.stack_placement.height
    slot = node.layout_slot
    if slot is not None and slot.positioned_pins is not None:
        fields = _positioned_fields_from_pins(
            slot.positioned_pins,
            render_boundary=node.render_boundary,
            parent_height=parent_height,
        )
    else:
        fields = _positioned_fields(
            placement,
            render_boundary=node.render_boundary,
            parent_height=parent_height,
        )
    if _child_needs_positioned_bounds(node, widget):
        _ensure_positioned_stack_bounds(
            fields, node, placement, parent_height=parent_height
        )
    if _should_omit_positioned_height(node, parent_node=parent_node):
        fields[:] = [field for field in fields if not field.startswith("height:")]
    from figma_flutter_agent.generator.layout.responsive import (
        should_stretch_bottom_positioned_horizontal,
        stretch_positioned_fields_horizontal,
    )

    if placement is not None and should_stretch_bottom_positioned_horizontal(placement):
        stretch_positioned_fields_horizontal(fields)
    width, height = _node_layout_size(node, placement)
    _raw_width, effective_height = _effective_svg_dimensions(node, width, height)
    adjusted_top = _stroke_line_top_adjustment(node, placement, effective_height)
    if (
        adjusted_top is not None
        and placement.top is not None
        and adjusted_top != placement.top
    ):
        fields = [
            field if not field.startswith("top:") else f"top: {adjusted_top}"
            for field in fields
        ]
    fields_str = ", ".join(fields)
    child = widget
    slot_height = placement.height
    if (
        slot_height is not None
        and slot_height > 0
        and node.type in {NodeType.COLUMN, NodeType.ROW, NodeType.CONTAINER}
    ):
        child = _wrap_bounded_positioned_slot_child(
            child,
            node=node,
            parent_node=parent_node,
        )
    return f"Positioned({fields_str}, {figma_value_key_arg(node.id)}, child: {child})"


def _should_center_text_in_button_stack(
    parent_node: CleanDesignTreeNode | None,
    text_node: CleanDesignTreeNode,
) -> bool:
    from figma_flutter_agent.parser.interaction import _is_footer_link_text_node

    if parent_node is None or text_node.type != NodeType.TEXT:
        return False
    if _is_footer_link_text_node(text_node):
        return False
    font_size = text_node.style.font_size if text_node.style else None
    if font_size is not None and float(font_size) >= 22.0:
        return False
    if _is_skip_control_stack(parent_node):
        return False
    if parent_node.type == NodeType.BUTTON:
        from figma_flutter_agent.parser.interaction import (
            button_has_list_tile_row_body,
            button_stack_has_left_icon,
        )

        if button_has_list_tile_row_body(parent_node):
            return False
        if button_stack_has_left_icon(parent_node):
            return False
        return True
    if parent_node.type != NodeType.STACK:
        return False
    if stack_interaction_kind(parent_node) == "button":
        return True
    text_nodes = [
        item
        for item in _local_nodes(parent_node, 2)
        if item.type == NodeType.TEXT and item.text
    ]
    return _stack_spans_primary_button_and_footer_link(
        parent_node, text_nodes=text_nodes
    )


def _button_label_should_center_in_parent(
    parent_node: CleanDesignTreeNode,
    *,
    placement: StackPlacement,
    text_node: CleanDesignTreeNode,
) -> bool:
    """Center CTA copy in the full button when an icon sits left or the label is wide."""
    if button_stack_has_left_icon(parent_node):
        return True
    parent_width = parent_node.sizing.width
    text_width = (
        placement.width if placement.width is not None else text_node.sizing.width
    )
    if parent_width is None or text_width is None or parent_width <= 0:
        return False
    return float(text_width) >= float(parent_width) * 0.55


def _ensure_text_center_align(widget: str) -> str:
    """Add ``textAlign: TextAlign.center`` when the label is centered in a button row."""
    if "textAlign:" in widget:
        return widget
    if "Text(" in widget and "textScaler:" in widget:
        return widget.replace(
            "textScaler:", "textAlign: TextAlign.center, textScaler:", 1
        )
    return widget


def _position_button_stack_label(
    widget: str,
    *,
    text_node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> str:
    """Vertically center CTA labels inside absolute button stacks."""
    parent_height = parent_node.sizing.height
    parent_width = parent_node.sizing.width
    text_nodes = [
        item
        for item in _local_nodes(parent_node, 2)
        if item.type == NodeType.TEXT and item.text
    ]
    if _stack_spans_primary_button_and_footer_link(parent_node, text_nodes=text_nodes):
        surface = primary_surface_node(parent_node)
        if surface is not None:
            if surface.sizing.height is not None and surface.sizing.height > 0:
                parent_height = surface.sizing.height
            if surface.sizing.width is not None and surface.sizing.width > 0:
                parent_width = surface.sizing.width
    if parent_height is None or parent_height <= 0:
        return _apply_stack_position(
            text_node,
            widget,
            parent_type=NodeType.STACK,
            fill_parent=False,
        )
    center_in_parent = _button_label_should_center_in_parent(
        parent_node,
        placement=placement,
        text_node=text_node,
    )
    if not center_in_parent:
        action_labels = [
            item
            for item in text_nodes
            if _label_matches_action_hint(
                (item.text or item.name or "").strip().lower()
            )
            and not _is_footer_link_text_node(item)
        ]
        if (
            stack_interaction_kind(parent_node) == "button"
            and len(text_nodes) == 1
            and len(action_labels) == 1
        ):
            center_in_parent = True
        else:
            center_in_parent = _stack_spans_primary_button_and_footer_link(
                parent_node,
                text_nodes=text_nodes,
            )
    if center_in_parent and parent_width is not None and parent_width > 0:
        fields = [
            "left: 0.0",
            f"width: {format_geometry_literal(parent_width)}",
            "top: 0.0",
            f"height: {format_geometry_literal(parent_height)}",
        ]
        label_widget = _ensure_text_center_align(widget)
        centered = f"Align(alignment: Alignment.center, child: {label_widget})"
    else:
        left = placement.left if placement.left is not None else 0.0
        width = (
            placement.width if placement.width is not None else text_node.sizing.width
        )
        fields = [
            f"left: {format_geometry_literal(left)}",
            "top: 0.0",
            f"height: {format_geometry_literal(parent_height)}",
        ]
        if width is not None and width > 0:
            fields.insert(1, f"width: {format_geometry_literal(width)}")
        centered = f"Align(alignment: Alignment.centerLeft, child: {widget})"
    return f"Positioned({', '.join(fields)}, {figma_value_key_arg(text_node.id)}, child: {centered})"


def _wrap_link_text(widget: str) -> str:
    """Wrap a text widget with a tappable link affordance."""
    return (
        "MouseRegion("
        "cursor: SystemMouseCursors.click, "
        f"child: GestureDetector(onTap: () {{}}, behavior: HitTestBehavior.opaque, child: {widget})"
        ")"
    )


def _button_ink_surface_params(
    surface: CleanDesignTreeNode,
) -> tuple[str | None, str | None]:
    """Return fill color and optional border for Material ``Ink`` on tap targets."""
    from figma_flutter_agent.generator.layout.style import (
        _border_color_expr,
        _resolved_border_width,
    )

    fill = (
        dart_color_expr(surface.style)
        if surface.style.background_color is not None
        else "const Color(0xFFFFFFFF)"
    )
    border = None
    border_width = surface.style.border_width or 0.0
    border_color = _border_color_expr(surface.style)
    if (
        border_color is not None
        and border_width > 0
        and (surface.style.opacity is None or surface.style.opacity > 0.01)
    ):
        resolved_width = _resolved_border_width(
            border_width,
            stroke_align=surface.style.stroke_align,
        )
        border = f"Border.all(color: {border_color}, width: {resolved_width})"
    return fill, border


def _is_consent_checkbox_row_stack(node: CleanDesignTreeNode) -> bool:
    """Synthetic row from ``reconcile_consent_checkbox_rows_in_tree``."""
    return node.type == NodeType.STACK and (
        node.name == "ConsentRow" or str(node.id).endswith("-consent-row")
    )


def _try_render_consent_checkbox_row(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Render privacy copy and checkbox as one tappable row."""
    if not _is_consent_checkbox_row_stack(node):
        return None
    checkbox_child = next(
        (child for child in node.children if looks_like_checkbox_control(child)),
        None,
    )
    label_child = next(
        (child for child in node.children if child.type == NodeType.TEXT),
        None,
    )
    if checkbox_child is None or label_child is None:
        return None
    align = text_align_expr(label_child.style)
    align_suffix = f", textAlign: {align}" if align else ""
    if label_child.text_spans:
        span_parts = emit_text_span_children_from_node(
            label_child,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        text_widget = emit_text_rich(span_parts, text_align_suffix=align_suffix)
    else:
        text = escape_dart_string(label_child.text or label_child.name)
        style_expr = text_style_expr(
            label_child,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        text_widget = (
            f"Text('{text}', style: {style_expr}, "
            f"{text_widget_trailing_params(label_child.style, text_align_suffix=align_suffix)})"
        )
    if is_link_text(label_child.text):
        text_widget = _wrap_link_text(text_widget)
    checkbox_widget = render_checkbox(checkbox_child, theme_variant=theme_variant)
    return (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [Expanded(child: {text_widget}), {checkbox_widget}]"
        ")"
    )


def _try_render_cta_footer_split_stack(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str,
    cluster_classes: dict[str, str] | None,
    cluster_vector_variants: dict[str, ClusterVectorVariant] | None,
    cluster_vector_variant: ClusterVectorVariant | None,
    skip_cluster_id: str | None,
    responsive_enabled: bool,
    design_artboard_width: float | None = None,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Render CTA pill + footer link as separate vertical bands with one InkWell on the pill."""
    if node.type != NodeType.STACK:
        return None
    text_nodes = [
        item
        for item in _local_nodes(node, 2)
        if item.type == NodeType.TEXT and item.text
    ]
    if not _stack_spans_primary_button_and_footer_link(node, text_nodes=text_nodes):
        return None
    surface = primary_surface_node(node)
    clip_height = float(surface.sizing.height or 0) if surface is not None else 0.0
    if clip_height <= 0:
        return None
    stack_width = node.sizing.width
    if node.stack_placement is not None and node.stack_placement.width is not None:
        stack_width = node.stack_placement.width
    if stack_width is None or stack_width <= 0:
        return None
    sorted_children = _sort_absolute_stack_children(node.children, is_layout_root=False)
    cta_children = [
        child
        for child in sorted_children
        if not (child.type == NodeType.TEXT and _is_footer_link_text_node(child))
    ]
    if surface is not None:
        cta_children = [child for child in cta_children if child.id != surface.id]
    footer_children = [
        child
        for child in sorted_children
        if child.type == NodeType.TEXT and _is_footer_link_text_node(child)
    ]
    if not cta_children or not footer_children:
        return None
    cta_widgets = [
        render_node_body(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
            parent_node=node,
            theme_variant=theme_variant,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
            cluster_vector_variant=cluster_vector_variant,
            skip_cluster_id=skip_cluster_id,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        for child in cta_children
    ]
    cta_body = ", ".join(cta_widgets)
    cta_stack = _wrap_button_stack(
        f"Stack(clipBehavior: Clip.hardEdge, children: [{cta_body}])",
        node,
        theme_variant=theme_variant,
    )
    parts = [
        (
            "Positioned(left: 0.0, top: 0.0, "
            f"width: {format_geometry_literal(stack_width)}, "
            f"height: {format_geometry_literal(clip_height)}, "
            f"child: {cta_stack})"
        ),
    ]
    for footer in footer_children:
        parts.append(
            render_node_body(
                footer,
                uses_svg=uses_svg,
                parent_type=NodeType.STACK,
                parent_node=node,
                theme_variant=theme_variant,
                cluster_classes=cluster_classes,
                cluster_vector_variants=cluster_vector_variants,
                cluster_vector_variant=cluster_vector_variant,
                skip_cluster_id=skip_cluster_id,
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            ),
        )
    return f"Stack(clipBehavior: Clip.none, children: [{', '.join(parts)}])"


def _stack_uses_circular_ink(node: CleanDesignTreeNode) -> bool:
    """Round tap targets (play/pause, skip, compact chrome) need ``CircleBorder`` ripples."""
    if looks_like_play_pause_control_stack(node) or looks_like_skip_control_stack(node):
        return True
    if _sizing_like_skip_control(node):
        return True
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if abs(float(width) - float(height)) > 3.0:
        return False
    size = min(float(width), float(height))
    if size < 28.0 or size > 120.0:
        return False
    if _has_circular_container(_descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)):
        return True
    surface = primary_surface_node(node)
    if surface is not None:
        radius = surface.style.border_radius
        if radius is not None and radius >= size / 2.2:
            return True
    return looks_like_compact_icon_action_stack(node)


def _wrap_button_stack(
    stack_widget: str,
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    tap_role: str = "button-action",
) -> str:
    """Wrap an interactive stack with a theme-appropriate tap target."""
    from figma_flutter_agent.generator.layout.style import _resolved_border_radius

    surface = interaction_surface_node(node)
    radius = (
        surface.style.border_radius
        if surface is not None and surface.style.border_radius is not None
        else node.style.border_radius
    )
    resolved_radius = _resolved_border_radius(
        surface.style if surface is not None else node.style,
        frame_width=node.sizing.width,
        frame_height=node.sizing.height,
    )
    if resolved_radius is not None:
        radius = resolved_radius
    ink_fill: str | None = None
    ink_border: str | None = None
    if surface is not None:
        ink_fill, ink_border = _button_ink_surface_params(surface)
    if _stack_uses_circular_ink(node) and ink_fill is None:
        wrapped = cupertino_wrap_circular_button_stack(
            stack_widget,
            theme_variant=theme_variant,
            node_id=node.id,
            tap_role=tap_role,
        )
        if variant_blocks_interaction(node):
            return wrapped.replace(
                f"onTap: () {{ {inline_custom_code_comment(custom_code_zone_id(node.id, tap_role))} }}, ",
                "onTap: null, ",
                1,
            )
        return wrapped
    wrapped = cupertino_wrap_button_stack(
        stack_widget,
        theme_variant=theme_variant,
        border_radius=radius,
        ink_fill_color=ink_fill,
        ink_border=ink_border,
        node_id=node.id,
        tap_role=tap_role,
    )
    if variant_blocks_interaction(node):
        wrapped = wrapped.replace(
            f"onTap: () {{ {inline_custom_code_comment(custom_code_zone_id(node.id, tap_role))} }}, ",
            "onTap: null, ",
            1,
        )
    from figma_flutter_agent.parser.interaction import (
        button_has_composite_row_body,
        button_has_list_tile_row_body,
    )

    intrinsic_height = button_has_composite_row_body(
        node
    ) or button_has_list_tile_row_body(node)
    width = node.sizing.width
    height = node.sizing.height
    if width is not None and height is not None and width > 0 and height > 0:
        width_lit = format_geometry_literal(width)
        height_lit = format_geometry_literal(height)
        if node.sizing.width_mode == SizingMode.FILL:
            if intrinsic_height:
                return f"SizedBox(width: double.infinity, child: {wrapped})"
            return (
                f"SizedBox(width: double.infinity, height: {height_lit}, "
                f"child: {wrapped})"
            )
        if intrinsic_height:
            return f"SizedBox(width: {width_lit}, child: {wrapped})"
        return (
            f"SizedBox(width: {width_lit}, height: {height_lit}, child: {wrapped})"
        )
    if node.sizing.width_mode == SizingMode.FILL or (
        width is not None and width >= 64.0
    ):
        if intrinsic_height:
            return f"SizedBox(width: double.infinity, child: {wrapped})"
        height_clause = ""
        if height is not None and height > 0:
            height_clause = f"height: {format_geometry_literal(height)}, "
        return (
            f"SizedBox(width: double.infinity, {height_clause}"
            f"child: {wrapped})"
        )
    return wrapped


def _wrap_accessibility(node: CleanDesignTreeNode, widget: str) -> str:
    if node.type in {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.DIALOG,
        NodeType.SLIDER,
    }:
        return widget
    if not node.accessibility_label:
        return widget
    label = escape_dart_string(node.accessibility_label)
    return f"Semantics(label: '{label}', child: {widget})"


def _wrap_min_touch_target(node: CleanDesignTreeNode, widget: str) -> str:
    from figma_flutter_agent.generator.layout.flex_policy import (
        row_is_tight_horizontal_pill_label,
    )
    from figma_flutter_agent.parser.interaction import (
        looks_like_input_trailing_icon_button,
    )

    if looks_like_input_trailing_icon_button(node):
        return widget
    if node.type == NodeType.BUTTON and node.children:
        row_host = node.children[0]
        if row_host.type == NodeType.ROW and row_is_tight_horizontal_pill_label(row_host):
            return widget
        width = node.sizing.width
        height = node.sizing.height
        if (
            width is not None
            and height is not None
            and width > 0
            and height > 0
            and float(width) > float(height) * 1.15
        ):
            return widget
    target = node.min_touch_target
    if target is None or target <= 0:
        return widget
    size = format_geometry_literal(target)
    return f"SizedBox(width: {size}, height: {size}, child: Center(child: {widget}))"


def _wrap_non_interactive_screen_chrome(node: CleanDesignTreeNode, widget: str) -> str:
    from figma_flutter_agent.parser.stack_paint import _is_bottom_screen_chrome

    if node.type == NodeType.BOTTOM_NAV:
        return widget
    if _is_bottom_screen_chrome(node):
        return f"IgnorePointer(ignoring: true, child: {widget})"
    return widget


def _should_offer_render_boundary_tap(node: CleanDesignTreeNode) -> bool:
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    if width <= 0.0 or height <= 0.0:
        return False
    area = width * height
    if area > 250_000.0:
        return False
    if area < 12_000.0:
        return bool(node.vector_asset_key and 1_600.0 <= area <= 12_000.0)
    placement = node.stack_placement
    return not (
        placement is not None and (placement.top or 0.0) < 280.0 and area > 80_000.0
    )


def _wrap_render_boundary_tap(node: CleanDesignTreeNode, widget: str) -> str:
    if not _should_offer_render_boundary_tap(node):
        return widget
    return (
        "GestureDetector("
        f"onTap: () {{ {inline_custom_code_comment(custom_code_zone_id(node.id, 'card-action'))} }}, "
        "behavior: HitTestBehavior.opaque, "
        f"child: {widget})"
    )


def _wrap_group_opacity(node: CleanDesignTreeNode, widget: str) -> str:
    """Apply frame opacity to the whole subtree (FID-12)."""
    opacity = node.style.opacity
    if opacity is None or opacity >= 1.0 - 1e-6 or opacity <= 0.0:
        return widget
    value = format_micro_style_literal(opacity)
    return f"Opacity(opacity: {value}, child: {widget})"


def _finalize_widget(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None = None,
    fill_parent: bool = False,
    scroll_content_root: bool = False,
) -> str:
    wrapped = _wrap_accessibility(node, widget)
    wrapped = _wrap_group_opacity(node, wrapped)
    wrapped = _wrap_content_layer_blur(node, wrapped)
    wrapped = _wrap_min_touch_target(node, wrapped)
    wrapped = _wrap_non_interactive_screen_chrome(node, wrapped)
    wrapped = _wrap_sizing(
        node, wrapped, parent_type=parent_type, parent_node=parent_node
    )
    from figma_flutter_agent.generator.layout.flex_policy import (
        post_flex_layout_slot_extents,
        prepare_flex_child_extents,
    )

    wrapped = prepare_flex_child_extents(
        wrapped,
        parent_type=parent_type,
        node=node,
    )
    wrapped = _apply_layout_slot_wraps(
        node,
        wrapped,
        parent_type=parent_type,
        parent_node=parent_node,
    )
    wrapped = post_flex_layout_slot_extents(
        wrapped,
        parent_type=parent_type,
        node=node,
        parent_node=parent_node,
    )
    return _apply_stack_position(
        node,
        wrapped,
        parent_type=parent_type,
        parent_node=parent_node,
        fill_parent=fill_parent,
        scroll_content_root=scroll_content_root,
    )


def render_node_body(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    parent_type: NodeType | None = None,
    parent_node: CleanDesignTreeNode | None = None,
    theme_variant: str = "material_3",
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict[str, ClusterVectorVariant] | None = None,
    cluster_vector_variant: ClusterVectorVariant | None = None,
    skip_cluster_id: str | None = None,
    responsive_enabled: bool = False,
    is_layout_root: bool = False,
    design_artboard_width: float | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    de_archetype_pass: bool = False,
    scroll_content_root: bool = False,
) -> str:
    """Render a Dart widget expression for a clean-tree node."""
    if not de_archetype_pass and _is_logo_wordmark_stack(node):
        return _finalize_widget(
            node,
            _render_logo_wordmark_stack(
                node,
                uses_svg=uses_svg,
                theme_variant=theme_variant,
                cluster_classes=cluster_classes,
                cluster_vector_variants=cluster_vector_variants,
                cluster_vector_variant=cluster_vector_variant,
                skip_cluster_id=skip_cluster_id,
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            ),
            parent_type=parent_type,
        scroll_content_root=scroll_content_root,
        )

    if not de_archetype_pass:
        consent_row = _try_render_consent_checkbox_row(
            node,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if consent_row is not None:
            return _finalize_widget(node, consent_row, parent_type=parent_type, scroll_content_root=scroll_content_root)

    if node.type == NodeType.STACK:
        play_pause_early = (
            None if de_archetype_pass else _try_render_play_pause_stack(node)
        )
        if play_pause_early is not None:
            label = escape_dart_string(node.accessibility_label or node.name)
            play_pause_early = _wrap_button_stack(
                play_pause_early,
                node,
                theme_variant=theme_variant,
            )
            play_pause_early = f"Semantics(label: '{label}', child: {play_pause_early})"
            return _finalize_widget(node, play_pause_early, parent_type=parent_type, scroll_content_root=scroll_content_root)

    if node.render_boundary and node.vector_asset_key:
        exported = _render_exported_vector(node, uses_svg=uses_svg)
        if exported is not None:
            fill_parent = _should_center_in_parent_stack(node, parent_node)
            widget = _wrap_render_boundary_tap(node, exported)
            if fill_parent:
                widget = _wrap_centered_stack_child(node, widget)
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
            )

    if node.extracted_widget_ref:
        ref_name = node.extracted_widget_ref.strip()
        widget_expr = f"const {ref_name}()" if ref_name else "const SizedBox.shrink()"
        return _finalize_widget(
            node,
            widget_expr,
            parent_type=parent_type,
        scroll_content_root=scroll_content_root,
        )

    cluster_id = node.cluster_id
    from figma_flutter_agent.parser.interaction import list_tile_leading_icon_slot

    if list_tile_leading_icon_slot(
        node, parent_node, parent_type=parent_type
    ):
        icon_asset = node.vector_asset_key
        if icon_asset is None and cluster_id and cluster_vector_variants:
            variant = cluster_vector_variants.get(cluster_id)
            if variant is not None:
                icon_asset = variant.forward_asset
        width = node.sizing.width or 48.0
        height = node.sizing.height or 48.0
        background = node.style.background_color or "0xFFF6F6F2"
        radius = node.style.border_radius or 18.0
        if icon_asset is not None and uses_svg:
            glyph = _render_svg_picture(node, escape_dart_string(icon_asset))
        elif parent_node is not None and len(parent_node.children) > 1:
            from figma_flutter_agent.generator.layout.navigation import nav_icon_expr

            title_host = parent_node.children[1]
            glyph = nav_icon_expr(title_host, uses_svg=False)
        else:
            glyph = "const SizedBox.shrink()"
        widget = (
            f"Container(width: {format_geometry_literal(width)}, "
            f"height: {format_geometry_literal(height)}, "
            f"decoration: BoxDecoration(color: Color({background}), "
            f"borderRadius: BorderRadius.circular({format_geometry_literal(radius)})), "
            "child: Row(mainAxisAlignment: MainAxisAlignment.center, "
            f"crossAxisAlignment: CrossAxisAlignment.center, children: [{glyph}]))"
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    pruned_cluster_has_instance_asset = (
        cluster_id is not None
        and not node.children
        and bool(node.flatten_figma_node_ids)
        and bool(node.vector_asset_key)
    )
    if (
        cluster_classes
        and cluster_id
        and cluster_id in cluster_classes
        and cluster_id != skip_cluster_id
        and not pruned_cluster_has_instance_asset
    ):
        class_name = cluster_classes[cluster_id]
        variant = (
            cluster_vector_variants.get(cluster_id) if cluster_vector_variants else None
        )
        if variant is not None and _sizing_like_skip_control(node):
            from figma_flutter_agent.generator.cluster_variants import (
                cluster_reference_args,
            )

            args = cluster_reference_args(node, variant)
            widget_expr = (
                f"const {class_name}({args})" if args else f"const {class_name}()"
            )
            label = escape_dart_string(
                node.accessibility_label or node.name or class_name
            )
            return _finalize_widget(
                node,
                f"Semantics(label: '{label}', child: {widget_expr})",
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )
        if (
            not de_archetype_pass
            and not node.children
            and uses_svg
            and _sizing_like_skip_control(node)
        ):
            pruned = _try_render_pruned_cluster_skip_control(
                node,
                uses_svg=uses_svg,
                skip_cluster_id=skip_cluster_id,
                cluster_vector_variant=variant,
                theme_variant=theme_variant,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
            if pruned is not None:
                label = escape_dart_string(node.accessibility_label or node.name)
                return _finalize_widget(
                    node,
                    f"Semantics(label: '{label}', child: {pruned})",
                    parent_type=parent_type,
                scroll_content_root=scroll_content_root,
                )
        if variant is not None:
            args = cluster_reference_args(node, variant)
            if args:
                return _finalize_widget(
                    node,
                    f"{class_name}({args})",
                    parent_type=parent_type,
                scroll_content_root=scroll_content_root,
                )
        return _finalize_widget(node, f"const {class_name}()", parent_type=parent_type, scroll_content_root=scroll_content_root)

    if (
        not de_archetype_pass
        and node.type == NodeType.STACK
        and not node.children
        and _sizing_like_skip_control(node)
    ):
        variant = (
            cluster_vector_variants.get(node.cluster_id)
            if cluster_vector_variants and node.cluster_id
            else None
        )
        pruned = _try_render_pruned_cluster_skip_control(
            node,
            uses_svg=uses_svg,
            skip_cluster_id=skip_cluster_id,
            cluster_vector_variant=variant,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if pruned is not None:
            label = escape_dart_string(node.accessibility_label or node.name)
            return _finalize_widget(
                node,
                f"Semantics(label: '{label}', child: {pruned})",
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )

    if node.type == NodeType.STACK and not is_layout_root:
        from figma_flutter_agent.generator.layout.interactive import (
            render_time_wheel_picker_stack,
            render_weekday_chip_row,
        )
        from figma_flutter_agent.parser.interaction import (
            WEEKDAY_CHIP_ROW_NAME,
            looks_like_wheel_time_picker_stack,
        )

        if node.name == WEEKDAY_CHIP_ROW_NAME:
            return _finalize_widget(
                node,
                render_weekday_chip_row(node),
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )
        if looks_like_wheel_time_picker_stack(node):
            return _finalize_widget(
                node,
                render_time_wheel_picker_stack(node),
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )
        cta_footer_split = (
            None
            if de_archetype_pass
            else _try_render_cta_footer_split_stack(
                node,
                uses_svg=uses_svg,
                theme_variant=theme_variant,
                cluster_classes=cluster_classes,
                cluster_vector_variants=cluster_vector_variants,
                cluster_vector_variant=cluster_vector_variant,
                skip_cluster_id=skip_cluster_id,
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
        )
        if cta_footer_split is not None:
            return _finalize_widget(node, cta_footer_split, parent_type=parent_type, scroll_content_root=scroll_content_root)

    sorted_children = _sort_absolute_stack_children(
        node.children,
        is_layout_root=is_layout_root,
    )
    from figma_flutter_agent.generator.layout.flex_policy import (
        stack_child_ordinal_top,
        stack_is_card_metadata_host,
    )

    metadata_column_host = (
        not is_layout_root
        and node.type == NodeType.STACK
        and stack_is_card_metadata_host(node, parent_node=parent_node)
    )
    if metadata_column_host:
        sorted_children = sorted(
            sorted_children,
            key=lambda child: (stack_child_ordinal_top(child), child.id),
        )
    paired_circle_ids: set[str] = set()
    merged_thumb_widgets: list[str] = []
    omit_child_ids: set[str] = set()
    playback_seek_ids: set[str] = set()
    playback_decor_omit_ids: set[str] = set()
    if node.type == NodeType.STACK:
        playback_seek_ids = _playback_seek_vector_ids(node)
        if playback_seek_ids:
            playback_decor_omit_ids = _playback_seek_omit_child_ids(node)
    if node.type == NodeType.STACK:
        circle_pair = (
            _find_concentric_circle_pair(sorted_children)
            if not playback_seek_ids
            else None
        )
        if circle_pair is not None:
            outer, inner = circle_pair
            paired_circle_ids = {outer.id, inner.id}
            merged_thumb_widgets = _render_concentric_circle_thumb(
                outer,
                inner,
                stack_siblings=sorted_children,
            )
        if not is_layout_root and stack_interaction_kind(node) == "button":
            surface = primary_surface_node(node)
            if surface is not None:
                omit_child_ids.add(surface.id)
    if node.type == NodeType.BUTTON:
        surface = primary_surface_node(node)
        if surface is not None:
            omit_child_ids.add(surface.id)

    child_widgets = [
        render_node_body(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.COLUMN if metadata_column_host else node.type,
            parent_node=node,
            theme_variant=theme_variant,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
            cluster_vector_variant=cluster_vector_variant,
            skip_cluster_id=skip_cluster_id,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        for child in sorted_children
        if child.id not in paired_circle_ids
        and child.id not in omit_child_ids
        and child.id not in playback_seek_ids
        and child.id not in playback_decor_omit_ids
    ]
    if merged_thumb_widgets:
        child_widgets.extend(merged_thumb_widgets)
    playback_seek_widget: str | None = None
    if playback_seek_ids:
        playback_seek_widget = _render_playback_seek_slider(node)
    from figma_flutter_agent.generator.layout.flex_policy import (
        resolve_cross_axis_alignment,
        resolve_main_axis_alignment,
    )

    main_axis = resolve_main_axis_alignment(
        node,
        scroll_content_root=scroll_content_root,
    )

    cross_axis = resolve_cross_axis_alignment(
        node,
        parent_type=parent_type,
        cross=node.alignment.cross,
    )

    if node.type == NodeType.TEXT:
        from figma_flutter_agent.generator.layout.flex_policy import (
            text_in_card_metadata_rail,
        )

        align = text_align_expr(node.style)
        align_suffix = f", textAlign: {align}" if align else ""
        metadata_rail = text_in_card_metadata_rail(
            node,
            parent_node,
            parent_type=parent_type,
        )
        strut = strut_style_expr(node.style, omit_leading=metadata_rail)
        explicit_multiline = False
        if node.text_spans:
            span_parts = emit_text_span_children_from_node(
                node,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
            widget = emit_text_rich(
                span_parts,
                text_align_suffix=align_suffix,
                strut_style=strut,
            )
        else:
            text = escape_dart_string(node.text or node.name)
            style_expr = text_style_expr(
                node,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
                omit_line_height_for_strut=strut is not None,
            )
            column_widget = _render_explicit_multiline_text_lines(
                node,
                style_expr=style_expr,
                text_align_suffix=align_suffix,
            )
            explicit_multiline = column_widget is not None
            if explicit_multiline:
                widget = column_widget
            else:
                from figma_flutter_agent.generator.layout.flex_policy import (
                    row_is_tight_horizontal_pill_label,
                )

                text = escape_dart_string(node.text or node.name)
                pill_label = (
                    parent_node is not None
                    and parent_type == NodeType.ROW
                    and row_is_tight_horizontal_pill_label(parent_node)
                )
                trailing = text_widget_trailing_params(
                    node.style,
                    text_align_suffix=align_suffix,
                )
                widget = f"Text('{text}', style: {style_expr}, {trailing})"
                if pill_label:
                    widget = wrap_tight_chip_label(widget)
                elif metadata_rail:
                    widget = wrap_tight_chip_label(
                        widget,
                        align="Alignment.centerRight",
                    )
                    if parent_type == NodeType.ROW:
                        text_width = node.sizing.width
                        if text_width is not None and text_width > 0:
                            widget = (
                                f"SizedBox(width: {format_geometry_literal(text_width)}, "
                                f"child: Align(alignment: Alignment.centerRight, child: {widget}))"
                            )
        if (
            node.style.text_align == "LEFT"
            and node.sizing.width_mode == SizingMode.FILL
            and parent_type in {NodeType.COLUMN, NodeType.ROW}
        ):
            widget = (
                "SizedBox(width: double.infinity, child: "
                f"Align(alignment: Alignment.centerLeft, child: {widget}))"
            )
        elif (
            (node.style.text_align or "").upper() == "CENTER"
            and parent_type == NodeType.COLUMN
        ):
            widget = (
                "SizedBox(width: double.infinity, child: "
                f"Center(child: {widget}))"
            )
        text_width = node.sizing.width
        if (
            "\n" in (node.text or "")
            and text_width is not None
            and text_width > 0
            and node.sizing.width_mode != SizingMode.FILL
            and (node.style.text_align or "").upper() != "CENTER"
        ):
            widget = (
                f"SizedBox(width: {format_geometry_literal(text_width)}, child: {widget})"
            )
        if is_link_text(node.text):
            widget = _wrap_link_text(widget)
        if (
            parent_node is not None
            and parent_type in {NodeType.STACK, NodeType.BUTTON}
            and node.stack_placement is not None
            and _should_center_text_in_button_stack(parent_node, node)
        ):
            widget = _wrap_accessibility(node, widget)
            return _position_button_stack_label(
                widget,
                text_node=node,
                parent_node=parent_node,
                placement=node.stack_placement,
            )
        if parent_node is not None and _is_skip_control_stack(parent_node):
            placement = node.stack_placement
            style_expr = text_style_expr(
                node,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
            text = escape_dart_string(node.text or node.name)
            trailing = text_widget_trailing_params(
                node.style,
                text_align_suffix=", textAlign: TextAlign.center",
            )
            widget = f"Text('{text}', style: {style_expr}, {trailing})"
            widget = _wrap_accessibility(node, f"Center(child: {widget})")
            if placement is not None and parent_type == NodeType.STACK:
                fields = _positioned_fields(placement)
                _ensure_positioned_stack_bounds(fields, node, placement)
                numeral_top = _skip_control_numeral_top(parent_node, node, placement)
                fields = [
                    field if not field.startswith("top:") else f"top: {numeral_top}"
                    for field in fields
                ]
                return f"Positioned({', '.join(fields)}, child: {widget})"
            return widget
        node = _clamp_centered_text_to_parent_stack(node, parent_node)
        fill_parent = _should_center_in_parent_stack(node, parent_node)
        if fill_parent:
            widget = _wrap_centered_stack_child(node, widget)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            fill_parent=fill_parent,
        scroll_content_root=scroll_content_root,
        )

    if node.type in {NodeType.IMAGE, NodeType.VECTOR} and node.vector_asset_key:
        raw_asset = node.vector_asset_key
        if cluster_vector_variant and raw_asset in {
            cluster_vector_variant.forward_asset,
            cluster_vector_variant.backward_asset,
        }:
            widget = _render_svg_picture_variant(
                node,
                forward_asset=cluster_vector_variant.forward_asset,
                backward_asset=cluster_vector_variant.backward_asset,
                param_name=cluster_vector_variant.param_name,
            )
            fill_parent = _should_center_in_parent_stack(node, parent_node)
            if fill_parent:
                widget = _wrap_centered_stack_child(node, widget)
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                parent_node=parent_node,
                fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
            )

        exported = _render_exported_vector(node, uses_svg=uses_svg)
        if exported is not None:
            widget = exported
            fill_parent = _should_center_in_parent_stack(node, parent_node)
            if fill_parent:
                widget = _wrap_centered_stack_child(node, widget)
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                parent_node=parent_node,
                fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
            )

    if node.type in {NodeType.IMAGE, NodeType.VECTOR} and (
        node.style.layer_blur or node.vector_svg_has_filter
    ):
        widget = _render_native_blur_vector(node)
        fill_parent = _should_center_in_parent_stack(node, parent_node)
        if fill_parent:
            widget = _wrap_centered_stack_child(node, widget)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            fill_parent=fill_parent,
        scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.IMAGE and node.image_asset_key:
        asset = escape_dart_string(node.image_asset_key)
        return _finalize_widget(
            node, f"Image.asset('{asset}', fit: BoxFit.cover)", parent_type=parent_type
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.CHECKBOX:
        widget = render_checkbox(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.SWITCH:
        widget = render_switch(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.RADIO_GROUP:
        widget = render_radio_group(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.RADIO:
        widget = render_radio(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.DROPDOWN:
        widget = render_dropdown(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.DIALOG:
        widget = render_dialog(
            node, child_widgets=child_widgets, theme_variant=theme_variant
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.SLIDER:
        if _should_suppress_playback_slider_node(node, parent_node):
            return _finalize_widget(
                node,
                "const SizedBox.shrink()",
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )
        widget = render_slider(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.BUTTON:
        if child_widgets and looks_like_compact_icon_action_button(node):
            from figma_flutter_agent.parser.interaction import (
                looks_like_stroke_plus_icon,
                stroke_plus_icon_expr,
            )

            if looks_like_stroke_plus_icon(node):
                glyph = stroke_plus_icon_expr(node)
                tap_role = "button-action"
            else:
                glyph = _find_icon_glyph_expr(node)
                tap_role = "back-nav"
            if glyph is not None:
                stack_body = (
                    "Stack(clipBehavior: Clip.none, alignment: Alignment.center, "
                    f"children: [{glyph}])"
                )
            else:
                icon_body = ", ".join(child_widgets)
                stack_body = (
                    f"Stack(clipBehavior: Clip.none, alignment: Alignment.center, "
                    f"children: [{icon_body}])"
                )
            width = node.sizing.width
            height = node.sizing.height
            if (
                width is not None
                and height is not None
                and width > 0
                and height > 0
            ):
                stack_body = (
                    f"SizedBox("
                    f"width: {format_geometry_literal(width)}, "
                    f"height: {format_geometry_literal(height)}, "
                    f"child: {stack_body})"
                )
            widget = _wrap_button_stack(
                stack_body,
                node,
                theme_variant=theme_variant,
                tap_role=tap_role,
            )
            label = escape_dart_string(node.accessibility_label or node.name or "Back")
            widget = f"Semantics(label: '{label}', child: {widget})"
        elif child_widgets:
            label = escape_dart_string(
                node.accessibility_label or node.text or node.name or "Button"
            )
            from figma_flutter_agent.parser.interaction import (
                button_has_composite_row_body,
                button_has_list_tile_row_body,
            )

            if button_has_list_tile_row_body(node):
                stack_body = _button_list_tile_row_body(node, child_widgets)
            else:
                body = ", ".join(child_widgets)
                if (
                    len(child_widgets) == 1
                    and len(node.children) == 1
                    and node.children[0].type == NodeType.TEXT
                ):
                    body = _wrap_center_preserving_flex_parent_data(child_widgets[0])
                stack_fit = (
                    "StackFit.loose"
                    if button_has_composite_row_body(node)
                    else "StackFit.expand"
                )
                stack_body = (
                    "Stack("
                    "clipBehavior: Clip.none, "
                    f"fit: {stack_fit}, "
                    f"children: [{body}]"
                    ")"
                )
            stack_body = wrap_flex_auto_layout_padding(node, stack_body)
            widget = _wrap_button_stack(
                stack_body,
                node,
                theme_variant=theme_variant,
            )
            widget = f"Semantics(label: '{label}', child: {widget})"
        else:
            widget = render_button(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.INPUT:
        if child_widgets and input_children_are_presentational(node):
            trailing = input_trailing_chrome_nodes(node)
            if trailing:
                return _render_flex_input_with_trailing_chrome(
                    node,
                    trailing,
                    theme_variant=theme_variant,
                    parent_type=parent_type,
                    uses_svg=uses_svg,
                    bundled_font_families=bundled_font_families,
                    dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                    text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                    text_theme_size_slots=text_theme_size_slots,
                )
            return _render_stack_input(
                node,
                theme_variant=theme_variant,
                parent_type=parent_type,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
        if child_widgets:
            body = ", ".join(child_widgets) or "const SizedBox.shrink()"
            widget = f"Column(crossAxisAlignment: {cross_axis}, children: [{body}])"
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        widget = render_input(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.CONTAINER and looks_like_checkbox_control(node):
        widget = render_checkbox(node, theme_variant=theme_variant)
        width = node.sizing.width
        height = node.sizing.height
        if width is not None and height is not None and width > 0 and height > 0:
            widget = f"SizedBox(width: {width}, height: {height}, child: {widget})"
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.CARD:
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        elevation = card_elevation_expr(node.style)
        radius = border_radius_expr(node.style)
        widget = (
            f"Card("
            f"elevation: {elevation}, "
            f"shape: RoundedRectangleBorder(borderRadius: {radius}), "
            f"child: Padding("
            f"padding: const EdgeInsets.all(AppSpacing.md), "
            f"child: Column(crossAxisAlignment: {cross_axis}, children: [{body}])"
            f")"
            f")"
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.TABS:
        widget = render_tabs(child_widgets, node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.CAROUSEL:
        widget = render_carousel(child_widgets, node, parent_type=parent_type)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.BOTTOM_NAV:
        widget = render_bottom_navigation(
            node,
            uses_svg=uses_svg,
            theme_variant=theme_variant,
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.WRAP:
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        spacing = format_geometry_literal(node.spacing)
        widget = f"Wrap(spacing: {spacing}, runSpacing: {spacing}, children: [{body}])"
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.GRID:
        widget = render_grid_view(
            node,
            child_widgets,
            parent_type=parent_type,
            responsive_enabled=responsive_enabled,
            is_layout_root=is_layout_root,
            design_artboard_width=design_artboard_width,
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.ROW:
        if node.scroll_axis == "horizontal":
            widget = render_scroll_list(
                node,
                child_widgets,
                axis="horizontal",
                parent_type=parent_type,
            )
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        from figma_flutter_agent.generator.layout.common import is_centered_glyph_badge
        from figma_flutter_agent.generator.layout.flex_policy import (
            _row_usable_main_span,
            row_hosts_chip_beside_heading,
            row_is_status_pill_badge,
            row_is_tight_horizontal_pill_label,
        )

        if row_hosts_chip_beside_heading(node) and child_widgets:
            spacing_field = _flex_spacing_field(node)
            body = ", ".join(child_widgets)
            widget = (
                "Align("
                "alignment: Alignment.centerLeft, "
                f"child: Row(mainAxisSize: MainAxisSize.min, "
                f"mainAxisAlignment: {main_axis}, "
                f"crossAxisAlignment: {cross_axis}, "
                f"{spacing_field}children: [{body}]))"
            )
            widget = _wrap_widget_with_box_decoration(
                node,
                widget,
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
            )
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        if (
            row_is_tight_horizontal_pill_label(node) or row_is_status_pill_badge(node)
        ) and child_widgets:
            if len(child_widgets) == 1:
                body = (
                    "Row(mainAxisSize: MainAxisSize.min, "
                    "mainAxisAlignment: MainAxisAlignment.center, "
                    "crossAxisAlignment: CrossAxisAlignment.center, "
                    f"children: [{child_widgets[0]}])"
                )
            else:
                spacing_field = _flex_spacing_field(node)
                body = (
                    f"Row(mainAxisAlignment: {main_axis}, "
                    f"crossAxisAlignment: {cross_axis}, "
                    f"{spacing_field}children: [{', '.join(child_widgets)}])"
                )
            widget = _wrap_widget_with_box_decoration(
                node,
                body,
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
            )
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        if is_centered_glyph_badge(node) and len(node.children) == 1:
            text_body = render_node_body(
                node.children[0],
                uses_svg=uses_svg,
                parent_type=NodeType.STACK,
                parent_node=node,
                theme_variant=theme_variant,
                cluster_classes=cluster_classes,
                cluster_vector_variants=cluster_vector_variants,
                cluster_vector_variant=cluster_vector_variant,
                skip_cluster_id=skip_cluster_id,
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
                de_archetype_pass=de_archetype_pass,
            )
            widget = _wrap_widget_with_box_decoration(
                node,
                _wrap_center_preserving_flex_parent_data(text_body),
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
            )
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        if uses_svg and _should_prefer_exported_svg(node):
            exported = _render_exported_vector(node, uses_svg=uses_svg)
            if exported is not None:
                width = node.sizing.width
                height = node.sizing.height
                if (
                    width is not None
                    and height is not None
                    and width > 0
                    and height > 0
                ):
                    exported = (
                        f"SizedBox(width: {format_geometry_literal(width)}, "
                        f"height: {format_geometry_literal(height)}, "
                        f"child: {exported})"
                    )
                spacing_field = _flex_spacing_field(node)
                widget = (
                    f"Row(mainAxisAlignment: {main_axis}, "
                    f"crossAxisAlignment: {cross_axis}, "
                    f"{spacing_field}children: [{exported}])"
                )
                widget = _wrap_widget_with_box_decoration(
                    node,
                    widget,
                    responsive_enabled=responsive_enabled,
                    design_artboard_width=design_artboard_width,
                )
                return _finalize_widget(
                    node, widget, parent_type=parent_type, parent_node=parent_node
                , scroll_content_root=scroll_content_root)
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        spacing_field = _flex_spacing_field(node)
        widget = (
            f"Row(mainAxisAlignment: {main_axis}, crossAxisAlignment: {cross_axis}, "
            f"{spacing_field}children: [{body}])"
        )
        widget = _wrap_widget_with_box_decoration(
            node,
            widget,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.COLUMN:
        if node.scroll_axis == "both":
            widget = render_both_axis_scroll(
                node,
                child_widgets,
                parent_type=parent_type,
            )
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        scroll_axis = scroll_axis_for_list(node)
        if scroll_axis is not None:
            widget = render_scroll_list(
                node,
                child_widgets,
                axis=scroll_axis,
                parent_type=parent_type,
            )
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        if should_apply_responsive_column_reflow(
            responsive_enabled=responsive_enabled,
            scroll_axis=node.scroll_axis,
            is_layout_root=is_layout_root,
            parent_type=parent_type,
            child_widgets=child_widgets,
            contains_form_control=any(child.type == NodeType.INPUT for child in node.children),
            design_artboard_width=design_artboard_width,
        ):
            widget = wrap_responsive_root_column(
                main_axis=main_axis,
                cross_axis=cross_axis,
                child_widgets=child_widgets,
                design_artboard_width=design_artboard_width,
                spacing_field=_flex_spacing_field(node),
            )
        else:
            body = ", ".join(child_widgets) or "const SizedBox.shrink()"
            from figma_flutter_agent.generator.layout.flex_policy import (
                _column_is_text_primary,
                _column_peer_in_bounded_row,
                column_cross_to_align_expr,
                column_in_bounded_positioned_host,
                column_is_tight_stack_text_host,
            )

            if (
                len(node.children) == 1
                and node.children[0].type == NodeType.TEXT
                and parent_type == NodeType.ROW
            ):
                widget = f"Align(alignment: Alignment.centerLeft, child: {body})"
            elif column_is_tight_stack_text_host(node):
                cross = node.alignment.cross
                if _column_is_text_primary(node) and all(
                    child.type == NodeType.TEXT
                    and (child.style.text_align or "LEFT").upper() == "LEFT"
                    for child in node.children
                ):
                    align = "Alignment.centerLeft"
                else:
                    align = column_cross_to_align_expr(cross)
                widget = f"Align(alignment: {align}, child: {body})"
            else:
                spacing_field = _flex_spacing_field(node)
                main_size_field = (
                    "mainAxisSize: MainAxisSize.min, "
                    if scroll_content_root
                    or _column_peer_in_bounded_row(node, parent_node=parent_node)
                    or _column_is_text_primary(node)
                    or column_in_bounded_positioned_host(node)
                    else ""
                )
                widget = (
                    f"Column({main_size_field}mainAxisAlignment: {main_axis}, "
                    f"crossAxisAlignment: {cross_axis}, "
                    f"{spacing_field}children: [{body}])"
                )
        widget = _wrap_widget_with_box_decoration(
            node,
            widget,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
        )
        if is_layout_root:
            widget = _wrap_root_column_viewport(
                node,
                widget,
                responsive_enabled=responsive_enabled,
                theme_variant=theme_variant,
            )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.STACK:
        from figma_flutter_agent.assets.composite_icons import (
            is_composite_icon_export_node,
        )

        if uses_svg and is_composite_icon_export_node(node) and node.vector_asset_key:
            widget = _render_svg_picture(
                node,
                escape_dart_string(node.vector_asset_key),
            )
            fill_parent = _should_center_in_parent_stack(node, parent_node)
            if fill_parent:
                widget = _wrap_centered_stack_child(node, widget)
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
            )
        play_pause = _try_render_play_pause_stack(node)
        if play_pause is not None:
            label = escape_dart_string(node.accessibility_label or node.name)
            play_pause = _wrap_button_stack(
                play_pause, node, theme_variant=theme_variant
            )
            play_pause = f"Semantics(label: '{label}', child: {play_pause})"
            return _finalize_widget(node, play_pause, parent_type=parent_type, scroll_content_root=scroll_content_root)
        pruned_skip = _try_render_pruned_cluster_skip_control(
            node,
            uses_svg=uses_svg,
            skip_cluster_id=skip_cluster_id,
            cluster_vector_variant=cluster_vector_variant,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if pruned_skip is not None:
            label = escape_dart_string(node.accessibility_label or node.name)
            pruned_skip = f"Semantics(label: '{label}', child: {pruned_skip})"
            return _finalize_widget(node, pruned_skip, parent_type=parent_type, scroll_content_root=scroll_content_root)
        if not is_layout_root and looks_like_back_nav_stack(node):
            body = ", ".join(child_widgets) or "const SizedBox.shrink()"
            stack_widget = f"Stack(clipBehavior: Clip.none, children: [{body}])"
            if is_back_navigation_icon_stack(node):
                stack_widget = cupertino_wrap_back_nav_stack(
                    stack_widget,
                    theme_variant=theme_variant,
                    node_id=node.id,
                )
            else:
                stack_widget = _wrap_button_stack(
                    stack_widget,
                    node,
                    theme_variant=theme_variant,
                )
            return _finalize_widget(
                node,
                stack_widget,
                parent_type=parent_type,
                parent_node=parent_node,
            scroll_content_root=scroll_content_root,
            )
        if not is_layout_root and looks_like_skip_control_stack(node):
            body = ", ".join(child_widgets) or "const SizedBox.shrink()"
            stack_widget = f"Stack(clipBehavior: Clip.none, children: [{body}])"
            label = escape_dart_string(node.accessibility_label or node.name)
            stack_widget = _wrap_button_stack(
                stack_widget,
                node,
                theme_variant=theme_variant,
            )
            stack_widget = f"Semantics(label: '{label}', child: {stack_widget})"
            return _finalize_widget(
                node,
                stack_widget,
                parent_type=parent_type,
                parent_node=parent_node,
            scroll_content_root=scroll_content_root,
            )
        interaction = None if is_layout_root else stack_interaction_kind(node)
        if interaction == "input":
            return _render_stack_input(
                node,
                theme_variant=theme_variant,
                parent_type=parent_type,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
        stack_children = list(child_widgets)
        if playback_seek_widget is not None:
            stack_children.append(playback_seek_widget)
        body = ", ".join(stack_children) or "const SizedBox.shrink()"
        from figma_flutter_agent.generator.layout.flex_policy import (
            column_center_hug_child_wrap,
            column_child_should_center_hug,
            stack_child_ordinal_bottom,
            stack_child_ordinal_top,
            stack_flow_child_horizontal_wrap,
            stack_flow_child_vertical_extent_wrap,
            stack_should_flow_as_column,
        )

        if stack_should_flow_as_column(node):
            ordered_pairs = sorted(
                zip(sorted_children, stack_children, strict=True),
                key=lambda pair: (stack_child_ordinal_top(pair[0]), pair[0].id),
            )
            flow_parts: list[str] = []
            for index, (child, widget) in enumerate(ordered_pairs):
                if index > 0:
                    previous_child = ordered_pairs[index - 1][0]
                    gap = stack_child_ordinal_top(child) - stack_child_ordinal_bottom(
                        previous_child
                    )
                    if gap > 0.5:
                        flow_parts.append(
                            f"SizedBox(height: {format_geometry_literal(gap)})"
                        )
                flow_widget = stack_flow_child_horizontal_wrap(child, widget)
                flow_widget = stack_flow_child_vertical_extent_wrap(child, flow_widget)
                if column_child_should_center_hug(node, child):
                    flow_widget = column_center_hug_child_wrap(node, child, flow_widget)
                flow_parts.append(flow_widget)
            body = ", ".join(flow_parts) or "const SizedBox.shrink()"
            stack_widget = (
                "Column("
                "mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.stretch, "
                f"children: [{body}]"
                ")"
            )
        elif metadata_column_host:
            spacing_field = ""
            if len(stack_children) >= 2:
                from figma_flutter_agent.generator.layout.flex_policy import (
                    stack_child_ordinal_top,
                )

                ordered = sorted(
                    node.children,
                    key=lambda child: (stack_child_ordinal_top(child), child.id),
                )
                if len(ordered) >= 2:
                    first = ordered[0]
                    second = ordered[1]
                    first_height = first.sizing.height or 0.0
                    gap = stack_child_ordinal_top(second) - (
                        stack_child_ordinal_top(first) + first_height
                    )
                    if gap > 0:
                        spacing_field = (
                            f"spacing: {format_geometry_literal(gap)}, "
                        )
            stack_widget = (
                "Column("
                "mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.end, "
                f"{spacing_field}"
                f"children: [{body}]"
                ")"
            )
        else:
            stack_clip = (
                "Clip.none"
                if not is_layout_root or stack_needs_soft_clip(node)
                else "Clip.hardEdge"
            )
            stack_widget = f"Stack(clipBehavior: {stack_clip}, children: [{body}])"
        if interaction == "button":
            if len(child_widgets) == 1 and "InkWell(" in child_widgets[0]:
                stack_widget = child_widgets[0]
            else:
                stack_widget = _wrap_button_stack(
                    stack_widget, node, theme_variant=theme_variant
                )
        root_decoration = (
            box_decoration_expr(
                node.style,
                width=node.sizing.width,
                height=node.sizing.height,
            )
            if is_layout_root
            else None
        )
        if root_decoration is not None:
            stack_widget = (
                f"Container(decoration: {root_decoration}, child: {stack_widget})"
            )
        stack_widget = _wrap_root_stack_viewport(
            node,
            stack_widget,
            is_layout_root=is_layout_root,
            responsive_enabled=responsive_enabled,
            theme_variant=theme_variant,
        )
        return _finalize_widget(
            node,
            stack_widget,
            parent_type=parent_type,
            parent_node=parent_node,
        scroll_content_root=scroll_content_root,
        )

    if child_widgets:
        body = ", ".join(child_widgets)
        inner = f"Column(crossAxisAlignment: {cross_axis}, children: [{body}])"
        box_decoration = box_decoration_expr(
            node.style,
            width=node.sizing.width,
            height=node.sizing.height,
        )
        if box_decoration is not None and node.type in {
            NodeType.CONTAINER,
            NodeType.COLUMN,
            NodeType.ROW,
        }:
            inner = f"Container(decoration: {box_decoration}, child: {inner})"
        return _finalize_widget(node, inner, parent_type=parent_type, scroll_content_root=scroll_content_root)

    if uses_svg and _should_prefer_exported_svg(node):
        widget = _render_svg_picture(
            node, escape_dart_string(node.vector_asset_key or "")
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    leaf_surface = _render_leaf_surface(node)
    if leaf_surface is not None:
        return _finalize_widget(node, leaf_surface, parent_type=parent_type, scroll_content_root=scroll_content_root)

    glyph = _render_stroke_glyph_fallback(node)
    if glyph is not None:
        return _finalize_widget(node, glyph, parent_type=parent_type, scroll_content_root=scroll_content_root)

    return _finalize_widget(node, "const SizedBox.shrink()", parent_type=parent_type, scroll_content_root=scroll_content_root)
