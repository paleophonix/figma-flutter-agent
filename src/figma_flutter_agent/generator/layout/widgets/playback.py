"""Playback control rendering: play/pause, seek slider, skip controls."""

from __future__ import annotations

from figma_flutter_agent.generator.cluster_variants import ClusterVectorVariant
from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.figma_anchor import figma_value_key_arg
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.style import (
    dart_color_expr,
    is_dark_fill_color,
    text_style_expr,
)
from figma_flutter_agent.generator.render_units import (
    format_figma_blur_sigma_literal,
)
from figma_flutter_agent.parser.interaction import (
    looks_like_play_pause_control_stack,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .shared import _node_layout_size
from .svg import (
    _effective_svg_dimensions,
    _is_roughly_square,
    _node_rotation_rad,
    _render_svg_picture,
    _skip_control_numeral_top,
    _slider_thumb_top,
    _svg_fit_mode,
)


def _render_native_blur_vector(node: CleanDesignTreeNode) -> str:
    """Render blurred vectors with ``ImageFiltered`` when assets are unavailable (FID-41)."""
    width, height = _node_layout_size(node, node.stack_placement)
    blur = node.style.layer_blur or node.style.background_blur or 35.0
    sigma = format_figma_blur_sigma_literal(blur)
    color_expr = dart_color_expr(
        node.style,
        fallback="Theme.of(context).colorScheme.surface",
    )
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
        f"color: {color_expr}.withOpacity({opacity})))"
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
    color_expr = dart_color_expr(
        inner.style if inner.style.background_color else outer.style,
        fallback="Theme.of(context).colorScheme.onSurface",
    )
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
            f"color: {color_expr}.withOpacity(0.24), shape: BoxShape.circle)))"
        ),
        (
            f"Positioned(left: {format_geometry_literal(inner_left)}, "
            f"top: {format_geometry_literal(inner_top)}, "
            f"width: {format_geometry_literal(inner_width)}, "
            f"height: {format_geometry_literal(inner_height)}, "
            "child: Container("
            "decoration: BoxDecoration("
            f"color: {color_expr}, shape: BoxShape.circle)))"
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
    fallback_core = (
        palette[1]
        if palette is not None
        else "Theme.of(context).colorScheme.onSurface"
    )
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


def _skip_control_numeral_label(node: CleanDesignTreeNode) -> str | None:
    """Return a skip/rewind seconds label only from explicit TEXT children."""
    for child in node.children:
        if child.type != NodeType.TEXT or not child.text:
            continue
        label = child.text.strip()
        if label.isdigit() and len(label) <= 2:
            return label
    return None


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
    from figma_flutter_agent.parser.interaction import find_raster_photo_leaf

    if find_raster_photo_leaf(node) is not None:
        return None
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
    numeral = _skip_control_numeral_label(node)
    placement = node.stack_placement
    body = (
        "Stack(clipBehavior: Clip.none, children: ["
        f"Positioned(left: 0.0, top: 0.0, width: {format_geometry_literal(node.sizing.width or 38.8)}, "
        f"height: {format_geometry_literal(node.sizing.height or 39.0)}, "
        f"child: Semantics(label: 'Vector', child: {svg}))"
    )
    if numeral is not None:
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
                "color: Theme.of(context).colorScheme.onSurfaceVariant)"
            )
        numeral_top = (
            _skip_control_numeral_top(node, node, placement) if placement else 15.5
        )
        body += (
            ", Positioned("
            f"left: 11.4, top: {format_geometry_literal(numeral_top)}, width: 15.9, height: 13.0, "
            f"child: Semantics(label: '{numeral}', child: Center(child: Text('{numeral}', "
            f"style: {style_expr}, textScaler: textScaler, textAlign: TextAlign.center))))"
        )
    body += "])"
    from .button import _wrap_button_stack

    return _wrap_button_stack(body, node, theme_variant=theme_variant)


_PLAYBACK_SEEK_TRACK_MIN_WIDTH_PX = 200.0
_PLAYBACK_SEEK_TRACK_MAX_HEIGHT_PX = 32.0
_PLAYBACK_TIMESTAMP_MAX_LEN = 5


def _looks_like_media_seek_timestamp(text: str) -> bool:
    """Music-player elapsed/total stamps like ``0:00`` or ``12:34`` (no AM/PM)."""
    stripped = text.strip()
    if not stripped or len(stripped) > _PLAYBACK_TIMESTAMP_MAX_LEN:
        return False
    if ":" not in stripped:
        return False
    minutes, seconds = stripped.split(":", maxsplit=1)
    if not minutes.isdigit() or not seconds.isdigit():
        return False
    return len(seconds) == 2


def _playback_seek_vector_ids(node: CleanDesignTreeNode) -> set[str]:
    if node.type != NodeType.STACK:
        return set()
    has_timestamps = any(
        child.type == NodeType.TEXT
        and child.text
        and _looks_like_media_seek_timestamp(child.text)
        for child in node.children
    )
    if not has_timestamps:
        return set()
    vectors = [child for child in node.children if child.type == NodeType.VECTOR]
    if len(vectors) < 2:
        return set()
    wide = max(vectors, key=lambda item: float(item.sizing.width or 0))
    wide_width = float(wide.sizing.width or 0)
    wide_height = float(wide.sizing.height or 0)
    if wide_width < _PLAYBACK_SEEK_TRACK_MIN_WIDTH_PX:
        return set()
    if wide_height > _PLAYBACK_SEEK_TRACK_MAX_HEIGHT_PX:
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
    palette = _play_pause_palette(node)
    if palette is None:
        return (
            f"SizedBox(width: {width}, height: {height}, "
            "child: Icon(Icons.play_arrow, "
            "color: Theme.of(context).colorScheme.onSurface, size: 48.0))"
        )
    ring_color, core_color, bar_color = palette

    def _palette_color_expr(fill: str, *, theme_fallback: str) -> str:
        if fill.startswith("Theme.") or fill.startswith("Color("):
            return fill
        if fill.startswith("0x"):
            return f"Color({fill})"
        return theme_fallback

    ring_expr = _palette_color_expr(
        ring_color,
        theme_fallback="Theme.of(context).colorScheme.outline",
    )
    core_expr = _palette_color_expr(
        core_color,
        theme_fallback="Theme.of(context).colorScheme.onSurface",
    )
    bar_expr = _palette_color_expr(
        bar_color,
        theme_fallback="Theme.of(context).colorScheme.onPrimary",
    )
    bar_width = 6.5
    bar_height = 24.0
    outer_size = max(width, height)
    return (
        f"SizedBox(width: {width}, height: {height}, child: Stack("
        "alignment: Alignment.center, "
        "children: ["
        f"Container(width: {outer_size}, height: {outer_size}, decoration: BoxDecoration("
        f"color: {ring_expr}.withOpacity(0.35), shape: BoxShape.circle)), "
        f"Container(width: {core_width}, height: {core_width}, decoration: BoxDecoration("
        f"color: {core_expr}, shape: BoxShape.circle)), "
        "Row(mainAxisSize: MainAxisSize.min, children: ["
        f"Container(width: {bar_width}, height: {bar_height}, decoration: BoxDecoration("
        f"color: {bar_expr}, borderRadius: BorderRadius.circular(14.0))), "
        "const SizedBox(width: 6.0), "
        f"Container(width: {bar_width}, height: {bar_height}, decoration: BoxDecoration("
        f"color: {bar_expr}, borderRadius: BorderRadius.circular(14.0)))"
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
