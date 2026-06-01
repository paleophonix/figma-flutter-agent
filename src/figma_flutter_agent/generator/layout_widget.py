"""Per-node deterministic widget expressions for layout codegen."""

from __future__ import annotations

from figma_flutter_agent.generator.cluster_variants import (
    ClusterVectorVariant,
    cluster_reference_args,
)
from figma_flutter_agent.generator.emit_text_span import (
    emit_text_rich,
    emit_text_span_children_from_node,
)
from figma_flutter_agent.generator.figma_anchor import figma_value_key_arg
from figma_flutter_agent.generator.layout_common import escape_dart_string
from figma_flutter_agent.generator.layout_cupertino import (
    wrap_back_nav_stack as cupertino_wrap_back_nav_stack,
)
from figma_flutter_agent.generator.layout_cupertino import (
    wrap_button_stack as cupertino_wrap_button_stack,
)
from figma_flutter_agent.generator.layout_cupertino import (
    wrap_scroll_viewport,
)
from figma_flutter_agent.generator.layout_form import (
    render_button,
    render_checkbox,
    render_dialog,
    render_dropdown,
    render_input,
    render_radio,
    render_radio_group,
    render_slider,
    render_switch,
)
from figma_flutter_agent.generator.layout_navigation import (
    render_bottom_navigation,
    render_carousel,
    render_tabs,
)
from figma_flutter_agent.generator.layout_responsive import (
    should_apply_responsive_column_reflow,
    wrap_responsive_root_column,
)
from figma_flutter_agent.generator.layout_scroll import (
    render_both_axis_scroll,
    render_grid_view,
    render_scroll_list,
    scroll_axis_for_list,
)
from figma_flutter_agent.generator.layout_style import (
    border_radius_expr,
    box_decoration_expr,
    card_elevation_expr,
    dart_color_expr,
    has_box_decoration,
    is_dark_fill_color,
    text_align_expr,
    text_style_expr,
)
from figma_flutter_agent.parser.interaction import (
    input_hint_node,
    input_hint_text,
    is_link_text,
    looks_like_back_nav_stack,
    looks_like_checkbox_control,
    looks_like_media_controls_stack,
    looks_like_password_field_stack,
    primary_surface_node,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
    round_geometry,
)
from figma_flutter_agent.parser.stack_paint import (
    sort_absolute_stack_children as _sort_absolute_stack_children,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode, StackPlacement

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


def _is_skip_control_stack(parent_node: CleanDesignTreeNode) -> bool:
    """Detect skip/rewind stacks that pair an arc vector with a numeric label."""
    if parent_node.type != NodeType.STACK:
        return False
    has_vector = any(
        child.type == NodeType.VECTOR and (child.vector_asset_key or child.style.has_stroke)
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
    return "BoxFit.fill" if width and height else "BoxFit.contain"


def _vector_needs_baked_raster(node: CleanDesignTreeNode) -> bool:
    """Return True when an exported vector should prefer a baked PNG raster."""
    return bool(node.style.layer_blur or node.vector_svg_has_filter)


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
    if node.type != NodeType.CONTAINER:
        return False
    if node.style.gradient is not None:
        return True
    return node.rotation is not None and abs(node.rotation) > 1e-3


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
        parent_width <= _ICON_BUTTON_MAX_SIZE
        and parent_height <= _ICON_BUTTON_MAX_SIZE
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
    if parent_width is None or parent_height is None or parent_width <= 0 or parent_height <= 0:
        return False

    if node.type in {NodeType.VECTOR, NodeType.IMAGE}:
        node_width = node.sizing.width
        node_height = node.sizing.height
        if node_width is None or node_height is None:
            return False
        if node_width >= parent_width * 0.85 or node_height >= parent_height * 0.85:
            return False
        return _is_roughly_square(parent_width, parent_height, max_size=_ICON_BUTTON_MAX_SIZE)

    if node.type == NodeType.TEXT:
        if not _is_roughly_square(parent_width, parent_height, max_size=_OVERLAY_TEXT_MAX_SIZE):
            return False
        text = (node.text or "").strip()
        return bool(text) and text.isdigit() and len(text) <= 4
    return False


def _wrap_centered_stack_child(node: CleanDesignTreeNode, widget: str) -> str:
    """Center a child within a square Stack using optional glyph offset padding."""
    if node.type != NodeType.TEXT:
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


def _render_svg_picture(node: CleanDesignTreeNode, asset: str) -> str:
    """Render an SVG asset with explicit bounds when Figma provides them."""
    width, height = _node_layout_size(node, node.stack_placement)
    width, height = _effective_svg_dimensions(node, width, height)
    params = [f"'{asset}'"]
    if width is not None and width > 0:
        params.append(f"width: {width}")
    if height is not None and height > 0:
        params.append(f"height: {height}")
    fit = _svg_fit_mode(node, width, height)
    params.append(f"fit: {fit}")
    return f"SvgPicture.asset({', '.join(params)})"


def _render_native_blur_vector(node: CleanDesignTreeNode) -> str:
    """Render blurred vectors with native Flutter shadows instead of unsupported SVG filters."""
    width, height = _node_layout_size(node, node.stack_placement)
    color = node.style.background_color or "0xFFFFFFFF"
    blur_radius = node.style.layer_blur or 35.0
    spread_radius = round(blur_radius * 0.25, 1)
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
        shape = (
            f"borderRadius: BorderRadius.all(Radius.elliptical({width / 2.0}, {height / 2.0})), "
        )
    else:
        shape = ""
    size_prefix = f"{', '.join(size_parts)}, " if size_parts else ""
    widget = (
        f"Container({size_prefix}"
        f"decoration: BoxDecoration({shape}"
        f"color: const Color({color}).withOpacity({opacity}), "
        "boxShadow: [BoxShadow("
        f"color: const Color({color}).withOpacity({opacity}), "
        f"blurRadius: {blur_radius}, spreadRadius: {spread_radius})]))"
    )
    if node.rotation is not None and abs(node.rotation) > 1e-3:
        angle = format_micro_style_literal(node.rotation)
        return f"Transform.rotate(angle: {angle}, child: {widget})"
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
    left = outer_placement.left if outer_placement and outer_placement.left is not None else 0.0
    top = outer_placement.top if outer_placement and outer_placement.top is not None else 0.0
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
            if width is not None and height is not None and width <= 10.0 and height >= 15.0:
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


def _node_stack_bounds(node: CleanDesignTreeNode) -> tuple[float, float, float, float] | None:
    """Return left/top/right/bottom for an absolutely placed node."""
    placement = node.stack_placement
    width = node.sizing.width
    height = node.sizing.height
    if placement is None or width is None or height is None or width <= 0 or height <= 0:
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
        if bounds is not None and _is_play_pause_dark_fill(current.style.background_color):
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
        if bounds is not None and _is_play_pause_dark_fill(current.style.background_color):
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
    if node.children:
        return None
    if skip_cluster_id is not None and node.cluster_id == skip_cluster_id:
        return None
    if not _sizing_like_skip_control(node):
        return None
    asset = node.vector_asset_key
    if asset is None and cluster_vector_variant is not None:
        from figma_flutter_agent.generator.cluster_variants import cluster_skip_backward_by_placement

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
    numeral_top = _skip_control_numeral_top(node, node, placement) if placement else 15.5
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
    left = placement.left if placement is not None and placement.left is not None else 0.0
    top = placement.top if placement is not None and placement.top is not None else 0.0
    value = _playback_slider_value(node)
    slider = (
        f"Slider("
        f"value: {value}, "
        "onChanged: (value) { /* <custom-code:slider-action> */ }"
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
        return None
    core_spec = _play_pause_core_spec(node)
    if core_spec is None:
        return None
    core_width, core_color = core_spec
    palette = _play_pause_palette(node)
    ring_color = palette[0] if palette is not None else core_color
    bar_color = palette[2] if palette is not None else (bars[0].style.background_color or ring_color)
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


def _wrap_sizing(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
) -> str:
    from figma_flutter_agent.generator.layout_flex_policy import apply_flex_wrap_to_widget

    wrapped = apply_flex_wrap_to_widget(widget, parent_type=parent_type, node=node)
    if parent_type == NodeType.ROW and node.sizing.height_mode == SizingMode.FILL:
        return f"SizedBox(height: double.infinity, child: {wrapped})"
    return wrapped


def _positioned_fields(
    placement: StackPlacement,
    *,
    render_boundary: bool = False,
) -> list[str]:
    """Map Figma constraints to Positioned constructor fields.

    Flutter ``Positioned`` allows at most two of ``left``/``right``/``width`` (and
    ``top``/``bottom``/``height``). SCALE pins use explicit ``width``/``height`` when known.
    """
    def _g(value: float) -> str:
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

    if vertical == "TOP":
        fields.append(f"top: {_g(placement.top)}")
        if placement.height is not None and placement.height > 0:
            fields.append(f"height: {_g(placement.height)}")
    elif vertical == "BOTTOM":
        fields.append(f"bottom: {_g(placement.bottom)}")
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


def _ensure_positioned_stack_bounds(
    fields: list[str],
    node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> None:
    """Add explicit ``Positioned`` width/height pins from Figma frame size."""
    width, height = figma_positioned_dimensions(node, placement)
    left = placement.left if placement.left is not None else node.offset_x
    top = placement.top if placement.top is not None else node.offset_y
    if (
        left is not None
        and top is not None
        and width is not None
        and height is not None
    ):
        fields[:] = [
            f"left: {format_geometry_literal(left)}",
            f"top: {format_geometry_literal(top)}",
            f"width: {format_geometry_literal(width)}",
            f"height: {format_geometry_literal(height)}",
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
    width = node.sizing.width
    height = node.sizing.height
    if width is not None and width > 0 and height is not None and height > 0:
        return f"Container(width: {width}, height: {height}, decoration: {decoration})"
    if width is not None and width > 0:
        return f"Container(width: {width}, decoration: {decoration})"
    if height is not None and height > 0:
        return f"Container(height: {height}, decoration: {decoration})"
    return f"Container(decoration: {decoration})"


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
    artboard = f"SizedBox(width: {width}, height: {height}, child: {stack_widget})"
    if responsive_enabled:
        return (
            "FittedBox(\n"
            "      fit: BoxFit.scaleDown,\n"
            f"      child: {artboard},\n"
            "    )"
        )
    viewport = f"SingleChildScrollView(child: {artboard})"
    return wrap_scroll_viewport(viewport, theme_variant=theme_variant)


def _input_content_padding(
    surface: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    field_height: float | None,
) -> str | None:
    """Derive ``InputDecoration.contentPadding`` from Figma placeholder placement."""
    if surface is None or hint_node is None or field_height is None or field_height <= 0:
        return None
    placement = hint_node.stack_placement
    if placement is None:
        return None
    left = placement.left if placement.left is not None else 20.0
    top = (placement.top if placement.top is not None else 0.0) + (
        hint_node.style.glyph_top_offset or 0.0
    )
    text_height = hint_node.style.glyph_height or placement.height
    font_size = hint_node.style.font_size or 16.0
    line_height = hint_node.style.line_height or 1.0
    computed_height = font_size * line_height
    if text_height is None or text_height <= 0:
        text_height = computed_height
    bottom = max(0.0, field_height - top - text_height)
    right = left
    return f"contentPadding: EdgeInsets.fromLTRB({left}, {top}, {right}, {bottom})"


def _stack_input_decoration(
    surface: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    hint: str,
    *,
    field_height: float | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    surface_on_container: bool = False,
) -> str:
    """Build ``InputDecoration`` for heuristic input stacks."""
    hint_text = escape_dart_string(hint)
    fields = [f"hintText: '{hint_text}'"]
    if hint_node is not None:
        fields.append(
            f"hintStyle: {text_style_expr(hint_node, bundled_font_families=bundled_font_families, dart_weight_overrides_by_family=dart_weight_overrides_by_family, text_theme_slot_by_style_name=text_theme_slot_by_style_name, text_theme_size_slots=text_theme_size_slots)}"
        )
    if surface_on_container:
        padding = _input_content_padding(surface, hint_node, field_height)
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
            fields.append(f"contentPadding: EdgeInsets.symmetric(horizontal: {left}, vertical: 0)")
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
    return f"InputDecoration({', '.join(fields)})"


def _render_stack_input(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
) -> str:
    """Render a positioned ``TextField`` for classic absolute input groups."""
    surface = primary_surface_node(node)
    hint_node = input_hint_node(node)
    hint = input_hint_text(node)
    width, height = _node_layout_size(surface or node, node.stack_placement)
    field_height = surface.sizing.height if surface is not None else height
    decoration = _stack_input_decoration(
        surface,
        hint_node,
        hint,
        field_height=field_height,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        surface_on_container=surface is not None and surface.style.background_color is not None,
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
    field = f"TextField(obscureText: {obscure}, style: {input_style}, decoration: {decoration})"
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
    label = escape_dart_string(node.accessibility_label or hint)
    field = f"Semantics(label: '{label}', child: {field})"
    return _finalize_widget(node, field, parent_type=parent_type)


def _should_omit_positioned_height(node: CleanDesignTreeNode) -> bool:
    """Let multi-line TEXT grow past Figma frame height instead of clipping with ellipsis."""
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
        width is not None
        and height is not None
        and width <= 220.0
        and height <= 48.0
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


def _render_centered_figma_text_lines(
    node: CleanDesignTreeNode,
    *,
    style_expr: str,
    text_align_suffix: str,
) -> str | None:
    if node.text_spans:
        return None
    raw = (node.text or "").strip()
    if "\n" not in raw or node.style.text_align != "CENTER":
        return None
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if len(lines) < 2:
        return None
    line_widgets = [
        f"Text('{escape_dart_string(line)}', style: {style_expr}, textScaler: textScaler{text_align_suffix})"
        for line in lines
    ]
    return (
        "Column("
        "mainAxisSize: MainAxisSize.min, "
        "crossAxisAlignment: CrossAxisAlignment.stretch, "
        f"children: [{', '.join(line_widgets)}]"
        ")"
    )


def _apply_stack_position(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
    fill_parent: bool = False,
) -> str:
    if parent_type not in {NodeType.STACK, NodeType.BUTTON}:
        return widget
    if fill_parent:
        return f"Positioned.fill(child: {widget})"
    placement = node.stack_placement
    if placement is None and node.layout_positioning == "ABSOLUTE":
        placement = StackPlacement(left=node.offset_x, top=node.offset_y)
    if placement is None:
        return widget
    fields = _positioned_fields(placement, render_boundary=node.render_boundary)
    if _child_needs_positioned_bounds(node, widget):
        _ensure_positioned_stack_bounds(fields, node, placement)
    if _should_omit_positioned_height(node):
        fields[:] = [field for field in fields if not field.startswith("height:")]
    width, height = _node_layout_size(node, placement)
    _raw_width, effective_height = _effective_svg_dimensions(node, width, height)
    adjusted_top = _stroke_line_top_adjustment(node, placement, effective_height)
    if adjusted_top is not None and placement.top is not None and adjusted_top != placement.top:
        fields = [
            field if not field.startswith("top:") else f"top: {adjusted_top}" for field in fields
        ]
    fields_str = ", ".join(fields)
    return f"Positioned({fields_str}, {figma_value_key_arg(node.id)}, child: {widget})"


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
    fill = (
        dart_color_expr(surface.style)
        if surface.style.background_color is not None
        else "const Color(0xFFFFFFFF)"
    )
    border = None
    if surface.style.border_color and surface.style.border_width:
        border = (
            f"Border.all(color: {dart_color_expr(surface.style)}, "
            f"width: {surface.style.border_width})"
        )
    return fill, border


def _wrap_button_stack(
    stack_widget: str,
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
) -> str:
    """Wrap an interactive stack with a theme-appropriate tap target."""
    surface = primary_surface_node(node)
    radius = surface.style.border_radius if surface is not None else None
    ink_fill: str | None = None
    ink_border: str | None = None
    if surface is not None:
        ink_fill, ink_border = _button_ink_surface_params(surface)
    return cupertino_wrap_button_stack(
        stack_widget,
        theme_variant=theme_variant,
        border_radius=radius,
        ink_fill_color=ink_fill,
        ink_border=ink_border,
    )


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
    target = node.min_touch_target
    if target is None or target <= 0:
        return widget
    size = format_geometry_literal(target)
    return f"SizedBox(width: {size}, height: {size}, child: Center(child: {widget}))"


def _wrap_non_interactive_screen_chrome(node: CleanDesignTreeNode, widget: str) -> str:
    from figma_flutter_agent.parser.stack_paint import _is_bottom_screen_chrome

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
        if node.vector_asset_key and 1_600.0 <= area <= 12_000.0:
            return True
        return False
    placement = node.stack_placement
    if placement is not None and (placement.top or 0.0) < 280.0 and area > 80_000.0:
        return False
    return True


def _wrap_render_boundary_tap(node: CleanDesignTreeNode, widget: str) -> str:
    if not _should_offer_render_boundary_tap(node):
        return widget
    return (
        "GestureDetector("
        "onTap: () { /* <custom-code:card-action> */ }, "
        "behavior: HitTestBehavior.opaque, "
        f"child: {widget})"
    )


def _finalize_widget(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
    fill_parent: bool = False,
) -> str:
    wrapped = _wrap_accessibility(node, widget)
    wrapped = _wrap_min_touch_target(node, wrapped)
    wrapped = _wrap_non_interactive_screen_chrome(node, wrapped)
    wrapped = _wrap_sizing(node, wrapped, parent_type=parent_type)
    return _apply_stack_position(
        node,
        wrapped,
        parent_type=parent_type,
        fill_parent=fill_parent,
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
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
) -> str:
    """Render a Dart widget expression for a clean-tree node."""
    if _is_logo_wordmark_stack(node):
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
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            ),
            parent_type=parent_type,
        )

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
            )

    if node.extracted_widget_ref:
        ref_name = node.extracted_widget_ref.strip()
        widget_expr = f"const {ref_name}()" if ref_name else "const SizedBox.shrink()"
        return _finalize_widget(
            node,
            widget_expr,
            parent_type=parent_type,
        )

    cluster_id = node.cluster_id
    if (
        cluster_classes
        and cluster_id
        and cluster_id in cluster_classes
        and cluster_id != skip_cluster_id
    ):
        class_name = cluster_classes[cluster_id]
        variant = cluster_vector_variants.get(cluster_id) if cluster_vector_variants else None
        if not node.children and uses_svg and _sizing_like_skip_control(node):
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
                )
        if variant is not None:
            args = cluster_reference_args(node, variant)
            if args:
                return _finalize_widget(
                    node,
                    f"{class_name}({args})",
                    parent_type=parent_type,
                )
        return _finalize_widget(node, f"const {class_name}()", parent_type=parent_type)

    sorted_children = _sort_absolute_stack_children(
        node.children,
        is_layout_root=is_layout_root,
    )
    paired_circle_ids: set[str] = set()
    merged_thumb_widgets: list[str] = []
    omit_child_ids: set[str] = set()
    playback_seek_ids: set[str] = set()
    if node.type == NodeType.STACK and looks_like_media_controls_stack(node):
        playback_seek_ids = _playback_seek_vector_ids(node)
    if node.type == NodeType.STACK:
        circle_pair = _find_concentric_circle_pair(sorted_children)
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
            parent_type=node.type,
            parent_node=node,
            theme_variant=theme_variant,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
            cluster_vector_variant=cluster_vector_variant,
            skip_cluster_id=skip_cluster_id,
            responsive_enabled=responsive_enabled,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        for child in sorted_children
        if child.id not in paired_circle_ids
        and child.id not in omit_child_ids
        and child.id not in playback_seek_ids
    ]
    if merged_thumb_widgets:
        child_widgets.extend(merged_thumb_widgets)
    playback_seek_widget: str | None = None
    if playback_seek_ids:
        playback_seek_widget = _render_playback_seek_slider(node)
    main_axis = _MAIN_AXIS.get(node.alignment.main, "MainAxisAlignment.start")
    cross_axis = _CROSS_AXIS.get(node.alignment.cross, "CrossAxisAlignment.start")

    if node.type == NodeType.TEXT:
        align = text_align_expr(node.style)
        align_suffix = f", textAlign: {align}" if align else ""
        if node.text_spans:
            span_parts = emit_text_span_children_from_node(
                node,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
            widget = emit_text_rich(span_parts, text_align_suffix=align_suffix)
        else:
            text = escape_dart_string(node.text or node.name)
            style_expr = text_style_expr(
                node,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
            column_widget = _render_centered_figma_text_lines(
                node,
                style_expr=style_expr,
                text_align_suffix=align_suffix,
            )
            if column_widget is not None:
                widget = column_widget
            else:
                text = escape_dart_string(node.text or node.name)
                widget = (
                    f"Text('{text}', style: {style_expr}, textScaler: textScaler{align_suffix})"
                )
        if is_link_text(node.text):
            widget = _wrap_link_text(widget)
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
            widget = (
                f"Text('{text}', style: {style_expr}, textScaler: textScaler, "
                "textAlign: TextAlign.center)"
            )
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
        fill_parent = _should_center_in_parent_stack(node, parent_node)
        if fill_parent:
            widget = _wrap_centered_stack_child(node, widget)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            fill_parent=fill_parent,
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
                fill_parent=fill_parent,
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
                fill_parent=fill_parent,
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
        )

    if node.type == NodeType.IMAGE and node.image_asset_key:
        asset = escape_dart_string(node.image_asset_key)
        return _finalize_widget(
            node, f"Image.asset('{asset}', fit: BoxFit.cover)", parent_type=parent_type
        )

    if node.type == NodeType.CHECKBOX:
        widget = render_checkbox(node, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.SWITCH:
        widget = render_switch(node, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.RADIO_GROUP:
        widget = render_radio_group(node, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.RADIO:
        widget = render_radio(node, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.DROPDOWN:
        widget = render_dropdown(node, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.DIALOG:
        widget = render_dialog(node, child_widgets=child_widgets, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.SLIDER:
        widget = render_slider(node, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.BUTTON:
        if child_widgets:
            label = escape_dart_string(
                node.accessibility_label or node.text or node.name or "Button"
            )
            body = ", ".join(child_widgets)
            surface = primary_surface_node(node)
            radius = (
                surface.style.border_radius
                if surface is not None and surface.style.border_radius is not None
                else node.style.border_radius
            )
            stack_body = f"Stack(clipBehavior: Clip.none, children: [{body}])"
            widget = _wrap_button_stack(
                stack_body,
                node,
                theme_variant=theme_variant,
            )
            widget = f"Semantics(label: '{label}', child: {widget})"
        else:
            widget = render_button(node, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.INPUT:
        widget = render_input(node, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.CONTAINER and looks_like_checkbox_control(node):
        widget = render_checkbox(node, theme_variant=theme_variant)
        width = node.sizing.width
        height = node.sizing.height
        if width is not None and height is not None and width > 0 and height > 0:
            widget = f"SizedBox(width: {width}, height: {height}, child: {widget})"
        return _finalize_widget(node, widget, parent_type=parent_type)

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
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.TABS:
        widget = render_tabs(child_widgets, node, theme_variant=theme_variant)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.CAROUSEL:
        widget = render_carousel(child_widgets, node, parent_type=parent_type)
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.BOTTOM_NAV:
        widget = render_bottom_navigation(
            node,
            uses_svg=uses_svg,
            theme_variant=theme_variant,
        )
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.WRAP:
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        spacing = format_geometry_literal(node.spacing)
        widget = f"Wrap(spacing: {spacing}, runSpacing: {spacing}, children: [{body}])"
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.GRID:
        widget = render_grid_view(
            node,
            child_widgets,
            parent_type=parent_type,
            responsive_enabled=responsive_enabled,
            is_layout_root=is_layout_root,
        )
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.ROW:
        if node.scroll_axis == "horizontal":
            widget = render_scroll_list(
                node,
                child_widgets,
                axis="horizontal",
                parent_type=parent_type,
            )
            return _finalize_widget(node, widget, parent_type=parent_type)
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        widget = f"Row(mainAxisAlignment: {main_axis}, crossAxisAlignment: {cross_axis}, children: [{body}])"
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.COLUMN:
        if node.scroll_axis == "both":
            widget = render_both_axis_scroll(
                node,
                child_widgets,
                parent_type=parent_type,
            )
            return _finalize_widget(node, widget, parent_type=parent_type)
        scroll_axis = scroll_axis_for_list(node)
        if scroll_axis is not None:
            widget = render_scroll_list(
                node,
                child_widgets,
                axis=scroll_axis,
                parent_type=parent_type,
            )
            return _finalize_widget(node, widget, parent_type=parent_type)
        if should_apply_responsive_column_reflow(
            responsive_enabled=responsive_enabled,
            scroll_axis=node.scroll_axis,
            is_layout_root=is_layout_root,
            parent_type=parent_type,
            child_widgets=child_widgets,
        ):
            widget = wrap_responsive_root_column(
                main_axis=main_axis,
                cross_axis=cross_axis,
                child_widgets=child_widgets,
            )
        else:
            body = ", ".join(child_widgets) or "const SizedBox.shrink()"
            widget = (
                f"Column(mainAxisAlignment: {main_axis}, crossAxisAlignment: {cross_axis}, "
                f"children: [{body}])"
            )
        return _finalize_widget(node, widget, parent_type=parent_type)

    if node.type == NodeType.STACK:
        from figma_flutter_agent.assets.composite_icons import is_composite_icon_export_node

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
            )
        play_pause = _try_render_play_pause_stack(node)
        if play_pause is not None:
            label = escape_dart_string(node.accessibility_label or node.name)
            play_pause = _wrap_button_stack(play_pause, node, theme_variant=theme_variant)
            play_pause = f"Semantics(label: '{label}', child: {play_pause})"
            return _finalize_widget(node, play_pause, parent_type=parent_type)
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
            return _finalize_widget(node, pruned_skip, parent_type=parent_type)
        if not is_layout_root and looks_like_back_nav_stack(node):
            body = ", ".join(child_widgets) or "const SizedBox.shrink()"
            stack_widget = f"Stack(clipBehavior: Clip.none, children: [{body}])"
            stack_widget = cupertino_wrap_back_nav_stack(
                stack_widget,
                theme_variant=theme_variant,
            )
            return _finalize_widget(node, stack_widget, parent_type=parent_type)
        interaction = None if is_layout_root else stack_interaction_kind(node)
        if interaction == "input":
            return _render_stack_input(
                node,
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
        stack_widget = f"Stack(clipBehavior: Clip.none, children: [{body}])"
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
            stack_widget = f"Container(decoration: {root_decoration}, child: {stack_widget})"
        stack_widget = _wrap_root_stack_viewport(
            node,
            stack_widget,
            is_layout_root=is_layout_root,
            responsive_enabled=responsive_enabled,
            theme_variant=theme_variant,
        )
        return _finalize_widget(node, stack_widget, parent_type=parent_type)

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
        return _finalize_widget(node, inner, parent_type=parent_type)

    if uses_svg and _should_prefer_exported_svg(node):
        widget = _render_svg_picture(node, escape_dart_string(node.vector_asset_key or ""))
        return _finalize_widget(node, widget, parent_type=parent_type)

    leaf_surface = _render_leaf_surface(node)
    if leaf_surface is not None:
        return _finalize_widget(node, leaf_surface, parent_type=parent_type)

    return _finalize_widget(node, "const SizedBox.shrink()", parent_type=parent_type)
