"""Icon and vector helpers for interaction predicate detection."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .shared import (
    _BACK_NAV_DESCENDANT_DEPTH,
    _COMPACT_ICON_ACTION_MAX,
    _COMPACT_ICON_ACTION_MIN,
    _ICON_ACTION_NAME_HINTS,
    _INPUT_TRAILING_ICON_DESCENDANT_DEPTH,
    _STROKE_AXIS_MAX_THICKNESS,
    _STROKE_AXIS_MIN_SPAN,
    _descendant_nodes,
)


def layout_fact_favorite_glyph_vector(node: CleanDesignTreeNode) -> bool:
    """Filled compact vector shapes used as wishlist / heart affordances."""
    if node.type != NodeType.VECTOR:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (10.0 <= float(width) <= 20.0 and 10.0 <= float(height) <= 18.0):
        return False
    aspect = float(width) / max(float(height), 1.0)
    if aspect < 1.02 or aspect > 1.35:
        return False
    if node.style.has_stroke and not node.style.background_color:
        return False
    return bool(node.style.background_color)


def _has_compact_circular_painted_background(local_nodes: list[CleanDesignTreeNode]) -> bool:
    """Return True for light circular painted surfaces behind hero wishlist glyphs."""
    from figma_flutter_agent.generator.layout.style.colors import fill_luminance

    from .shared import _argb_color_key

    for item in local_nodes:
        background = _argb_color_key(item.style.background_color)
        if not background:
            continue
        width = item.sizing.width
        height = item.sizing.height
        if width is None or height is None:
            continue
        extent_w = float(width)
        extent_h = float(height)
        if extent_w < 20.0 or extent_h < 20.0:
            continue
        radius = float(item.style.border_radius or 0.0)
        if abs(extent_w - extent_h) > 4.0 and radius < min(extent_w, extent_h) * 0.35:
            continue
        luminance = fill_luminance(background)
        if luminance is not None and luminance >= 0.85:
            return True
    return False


def layout_fact_favorite_overlay_stack(node: CleanDesignTreeNode) -> bool:
    """Compact hero wishlist/save overlays modeled as STACK hosts, not BUTTON."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (28.0 <= float(width) <= 40.0 and 28.0 <= float(height) <= 40.0):
        return False
    local_nodes = _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)
    if not _has_compact_circular_painted_background(local_nodes):
        from figma_flutter_agent.generator.layout.style.colors import fill_luminance

        from .shared import _argb_color_key

        luminance = fill_luminance(_argb_color_key(node.style.background_color))
        if luminance is None or luminance < 0.85:
            return False
    if any(layout_fact_favorite_glyph_vector(item) for item in local_nodes):
        return True
    return any(
        item.vector_asset_key
        and item.type in {NodeType.VECTOR, NodeType.STACK, NodeType.CONTAINER}
        for item in local_nodes
    )


def _has_circular_container(local_nodes: list[CleanDesignTreeNode]) -> bool:
    for item in local_nodes:
        if item.type != NodeType.CONTAINER:
            continue
        width = item.sizing.width
        height = item.sizing.height
        if width is None or height is None:
            continue
        w = float(width)
        h = float(height)
        if w < 44.0 or h < 44.0:
            continue
        if abs(w - h) <= 4.0 or (item.style.border_radius or 0) >= 20.0:
            return True
    return False


def _has_icon_action_name(node: CleanDesignTreeNode) -> bool:
    labels = [
        (node.name or "").lower(),
        (node.accessibility_label or "").lower(),
    ]
    if node.variant is not None and node.variant.component_name:
        labels.append(node.variant.component_name.lower())
    combined = " ".join(labels)
    return any(hint in combined for hint in _ICON_ACTION_NAME_HINTS)


def _stack_has_vector_icon(local_nodes: list[CleanDesignTreeNode]) -> bool:
    return any(
        item.vector_asset_key
        or item.type == NodeType.VECTOR
        or (item.name or "").lower().startswith("vector")
        for item in local_nodes
    )


def _vector_paint_span(node: CleanDesignTreeNode) -> tuple[float, float]:
    """Return stroke vector paint width/height, using paint bounds when layout size is zero."""
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    frame = node.geometry_frame
    if frame is not None and frame.paint_rect is not None:
        if width <= 0:
            width = float(frame.paint_rect.width or 0.0)
        if height <= 0:
            height = float(frame.paint_rect.height or 0.0)
    return width, height


def _stroke_icon_vectors(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Collect stroke vectors under a compact icon host."""
    return [
        item
        for item in _descendant_nodes(node, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
        if item.type == NodeType.VECTOR and item.style.has_stroke
    ]


def _stroke_icon_size_expr(node: CleanDesignTreeNode) -> str:
    """Resolve Material icon size from a square icon button host."""
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    size = min(width, height) if width > 0 and height > 0 else 24.0
    size = max(min(size * 0.5, 24.0), 16.0)
    return format_geometry_literal(size)


def _stroke_icon_color_expr(
    vectors: list[CleanDesignTreeNode],
    *,
    host: CleanDesignTreeNode | None = None,
) -> str:
    from figma_flutter_agent.generator.layout.style import dart_color_expr, is_dark_fill_color

    theme_on_surface = "Theme.of(context).colorScheme.onSurface"
    theme_on_primary = "Theme.of(context).colorScheme.onPrimary"
    if not vectors:
        return theme_on_surface
    for vector in vectors:
        color = dart_color_expr(
            vector.style,
            css_key="border-color",
            fallback="",
        )
        if color and "onSurface" not in color and "onPrimary" not in color:
            if "FFFFFFFF" not in color.upper():
                return color
    if host is not None and is_dark_fill_color(host.style.background_color):
        return theme_on_primary
    return dart_color_expr(
        vectors[0].style,
        css_key="border-color",
        fallback=theme_on_surface,
    )


def passive_decorative_icon_glyph(node: CleanDesignTreeNode) -> bool:
    """Return True when a compact icon component is a passive tile glyph, not an action."""
    if node.type not in {NodeType.STACK, NodeType.CARD}:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (
        _COMPACT_ICON_ACTION_MIN <= float(width) <= _COMPACT_ICON_ACTION_MAX + 8.0
        and _COMPACT_ICON_ACTION_MIN <= float(height) <= _COMPACT_ICON_ACTION_MAX + 8.0
    ):
        return False
    if _has_icon_action_name(node):
        return False
    local_nodes = _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)
    if not _stack_has_vector_icon(local_nodes):
        return False
    if any(item.type == NodeType.TEXT and (item.text or "").strip() for item in local_nodes):
        return False
    if node.component_ref is not None:
        return True
    return node.type == NodeType.CARD


def layout_fact_compact_icon_action_stack(node: CleanDesignTreeNode) -> bool:
    """Small Figma icon components (e.g. 24x24 ``arrow-narrow-left``) used as back/close."""
    if passive_decorative_icon_glyph(node):
        return False
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (
        _COMPACT_ICON_ACTION_MIN <= width <= _COMPACT_ICON_ACTION_MAX
        and _COMPACT_ICON_ACTION_MIN <= height <= _COMPACT_ICON_ACTION_MAX
    ):
        return False
    local_nodes = _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)
    if not _stack_has_vector_icon(local_nodes):
        return False
    return _has_icon_action_name(node) or node.component_ref is not None


def layout_fact_info_icon_button(node: CleanDesignTreeNode) -> bool:
    """Circular info affordance: ring vector plus dot/stem vectors."""
    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (28.0 <= float(width) <= 36.0 and 28.0 <= float(height) <= 36.0):
        return False
    vectors = [
        item
        for item in _descendant_nodes(node, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
        if item.type == NodeType.VECTOR
    ]
    if len(vectors) < 2:
        return False
    has_ring = any(
        item.sizing.width is not None
        and item.sizing.height is not None
        and abs(float(item.sizing.width) - float(item.sizing.height)) <= 2.5
        and float(item.sizing.width) >= 10.0
        and item.style.has_stroke
        for item in vectors
    )
    has_marker = any(
        item.sizing.height is not None
        and float(item.sizing.height) <= 4.0
        and (item.sizing.width is None or float(item.sizing.width) <= 3.0)
        for item in vectors
    )
    return has_ring and has_marker


def layout_fact_compact_icon_action_button(node: CleanDesignTreeNode) -> bool:
    """Circular flex ``BUTTON`` frames that only host a chevron/close vector."""
    if layout_fact_info_icon_button(node):
        return False
    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (
        _COMPACT_ICON_ACTION_MIN <= width <= _COMPACT_ICON_ACTION_MAX + 28.0
        and _COMPACT_ICON_ACTION_MIN <= height <= _COMPACT_ICON_ACTION_MAX + 28.0
    ):
        return False
    return _stack_has_vector_icon(_descendant_nodes(node, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH))


def layout_fact_input_trailing_icon_button(node: CleanDesignTreeNode) -> bool:
    """Small square icon ``BUTTON`` embedded at the end of a flex ``INPUT`` row."""
    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (14.0 <= width <= 28.0 and 14.0 <= height <= 28.0):
        return False
    return _stack_has_vector_icon(_descendant_nodes(node, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH))


def layout_fact_stroke_plus_icon(node: CleanDesignTreeNode) -> bool:
    """Return True when a square icon button hosts perpendicular stroke vectors (plus)."""
    if node.type != NodeType.BUTTON:
        return False
    vectors = [
        item
        for item in _descendant_nodes(node, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
        if item.type == NodeType.VECTOR and item.style.has_stroke
    ]
    if len(vectors) < 2:
        return False
    horizontal = 0
    vertical = 0
    for vector in vectors:
        width, height = _vector_paint_span(vector)
        if height <= _STROKE_AXIS_MAX_THICKNESS and width >= _STROKE_AXIS_MIN_SPAN:
            horizontal += 1
        elif width <= _STROKE_AXIS_MAX_THICKNESS and height >= _STROKE_AXIS_MIN_SPAN:
            vertical += 1
    return horizontal >= 1 and vertical >= 1


def layout_fact_stroke_minus_icon(node: CleanDesignTreeNode) -> bool:
    """Return True when an icon host contains a single horizontal stroke bar."""
    vectors = _stroke_icon_vectors(node)
    if len(vectors) != 1:
        return False
    width, height = _vector_paint_span(vectors[0])
    return height <= _STROKE_AXIS_MAX_THICKNESS and width >= _STROKE_AXIS_MIN_SPAN


def layout_fact_stroke_close_icon(node: CleanDesignTreeNode) -> bool:
    """Return True when an icon host contains two small crossing stroke vectors."""
    vectors = _stroke_icon_vectors(node)
    if len(vectors) < 2:
        return False
    if layout_fact_stroke_plus_icon(node):
        return False
    spans = [_vector_paint_span(vector) for vector in vectors]
    compact = [
        (width, height)
        for width, height in spans
        if width >= 5.0 and height >= 5.0 and width <= 16.0 and height <= 16.0
    ]
    return len(compact) >= 2


def stroke_minus_icon_expr(node: CleanDesignTreeNode) -> str | None:
    """Material ``Icons.remove`` fallback for stroke-drawn minus affordances."""
    if not layout_fact_stroke_minus_icon(node):
        return None
    vectors = _stroke_icon_vectors(node)
    color = _stroke_icon_color_expr(vectors, host=node)
    size = _stroke_icon_size_expr(node)
    return f"Icon(Icons.remove, color: {color}, size: {size})"


def stroke_close_icon_expr(node: CleanDesignTreeNode) -> str | None:
    """Material ``Icons.close`` fallback for stroke-drawn dismiss affordances."""
    if not layout_fact_stroke_close_icon(node):
        return None
    vectors = _stroke_icon_vectors(node)
    color = _stroke_icon_color_expr(vectors, host=node)
    size = _stroke_icon_size_expr(node)
    return f"Icon(Icons.close, color: {color}, size: {size})"


def stroke_plus_icon_expr(node: CleanDesignTreeNode) -> str | None:
    """Material ``Icons.add`` fallback for stroke-drawn plus affordances."""
    if not layout_fact_stroke_plus_icon(node):
        return None
    vectors = _stroke_icon_vectors(node)
    if not vectors:
        return None
    color = _stroke_icon_color_expr(vectors, host=node)
    size = _stroke_icon_size_expr(node)
    return f"Icon(Icons.add, color: {color}, size: {size})"


_CATEGORY_TILE_MIN_SPAN = 80.0
_CATEGORY_TILE_MAX_SPAN = 120.0
_CATEGORY_ICON_SLOT_TOP_MAX = 28.0
_CATEGORY_ICON_SLOT_MIN = 20.0
_CATEGORY_ICON_SLOT_MAX = 36.0


def _category_component_host(node: CleanDesignTreeNode) -> bool:
    component_name = ""
    if node.variant is not None and node.variant.component_name:
        component_name = node.variant.component_name.strip().lower()
    elif node.name:
        component_name = node.name.strip().lower()
    if component_name == "category" or component_name.startswith("category "):
        return True
    return node.component_ref is not None and component_name.startswith("icon / category")


def _category_tile_icon_slot(child: CleanDesignTreeNode) -> bool:
    if passive_decorative_icon_glyph(child):
        placement = child.stack_placement
        top = float(placement.top or 0.0) if placement is not None else 0.0
        return top <= _CATEGORY_ICON_SLOT_TOP_MAX
    if child.type != NodeType.STACK:
        return False
    width = child.sizing.width
    height = child.sizing.height
    if width is None or height is None:
        return False
    if not (
        _CATEGORY_ICON_SLOT_MIN <= float(width) <= _CATEGORY_ICON_SLOT_MAX
        and _CATEGORY_ICON_SLOT_MIN <= float(height) <= _CATEGORY_ICON_SLOT_MAX
    ):
        return False
    if not _stack_has_vector_icon(_descendant_nodes(child, _BACK_NAV_DESCENDANT_DEPTH)):
        return False
    placement = child.stack_placement
    top = float(placement.top or 0.0) if placement is not None else 0.0
    return top <= _CATEGORY_ICON_SLOT_TOP_MAX


def layout_fact_stack_category_component_tile(node: CleanDesignTreeNode) -> bool:
    """Return True for square Category component tiles with top icon + lower label slots."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (
        _CATEGORY_TILE_MIN_SPAN <= float(width) <= _CATEGORY_TILE_MAX_SPAN
        and _CATEGORY_TILE_MIN_SPAN <= float(height) <= _CATEGORY_TILE_MAX_SPAN
    ):
        return False
    if not _category_component_host(node):
        return False
    has_icon_slot = any(_category_tile_icon_slot(child) for child in node.children)
    has_label = any(
        child.type == NodeType.TEXT and (child.text or "").strip() for child in node.children
    )
    return has_icon_slot and has_label


def layout_fact_stack_vertical_icon_label_chip_tile(node: CleanDesignTreeNode) -> bool:
    """Category chips with a square icon surface band and a lower label slot."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (48.0 <= float(width) <= 80.0 and 80.0 <= float(height) <= 120.0):
        return False
    if not _category_component_host(node):
        return False
    has_icon_slot = any(_category_tile_icon_slot(child) for child in node.children)
    label_nodes = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]
    if not has_icon_slot or len(label_nodes) != 1:
        return False
    placement = label_nodes[0].stack_placement
    if placement is None:
        return False
    top = placement.top if placement.top is not None else 0.0
    return top >= float(height) * 0.55
