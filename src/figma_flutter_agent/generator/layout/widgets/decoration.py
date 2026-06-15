"""Blur, shadow, box-decoration, and stroke-glyph fallback emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.scroll import (
    wrap_flex_auto_layout_padding,
)
from figma_flutter_agent.generator.layout.style import (
    border_radius_expr,
    box_decoration_expr,
    box_foreground_decoration_expr,
    dart_color_expr,
)
from figma_flutter_agent.generator.layout.style.decoration import _shadow_expr
from figma_flutter_agent.generator.render_units import (
    format_figma_blur_sigma_literal,
)
from figma_flutter_agent.parser.interaction import (
    looks_like_bottom_docked_sheet,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    SizingMode,
)

from .layout import _hoist_flex_parent_data
from .shared import _node_layout_size


def _render_stroke_glyph_fallback(node: CleanDesignTreeNode) -> str | None:
    """Material icon fallback for vectors missing exported SVG assets."""
    from figma_flutter_agent.parser.interaction import _vector_paint_span

    if node.type != NodeType.VECTOR or node.vector_asset_key:
        return None
    width, height = _vector_paint_span(node)
    if width <= 0 and height <= 0:
        return None
    has_stroke = node.style.has_stroke
    has_fill = bool(node.style.background_color)
    if not has_stroke and not has_fill:
        return None
    color = dart_color_expr(
        node.style,
        css_key="border-color" if has_stroke else "background-color",
        fallback="Theme.of(context).colorScheme.onSurfaceVariant",
    )
    if has_stroke and height >= width * 1.15 and width <= 14.0:
        # Figma reports tight vector bounds (e.g. 5×10); scale for ~48dp tap targets.
        chevron_size = min(max(width, height) * 2.4, 24.0)
        chevron_size = max(chevron_size, 18.0)
        return (
            f"Icon(Icons.chevron_left, color: {color}, "
            f"size: {format_geometry_literal(chevron_size)})"
        )
    if has_stroke and height <= 2.5 and width >= 8.0:
        size = max(min(width * 1.6, 24.0), 16.0)
        return f"Icon(Icons.remove, color: {color}, size: {format_geometry_literal(size)})"
    if has_stroke and width <= 2.5 and height >= 8.0:
        size = max(min(height * 1.6, 24.0), 16.0)
        return f"Icon(Icons.add, color: {color}, size: {format_geometry_literal(size)})"
    size = max(width, height, 12.0)
    from figma_flutter_agent.parser.interaction import looks_like_favorite_glyph_vector

    if looks_like_favorite_glyph_vector(node):
        return f"Icon(Icons.favorite_border, color: {color}, size: {format_geometry_literal(size)})"
    from figma_flutter_agent.parser.interaction import looks_like_info_icon_button

    if node.type == NodeType.BUTTON and looks_like_info_icon_button(node):
        icon_size = max(min(float(width or 32.0), float(height or 32.0)) * 0.45, 14.0)
        return (
            f"Icon(Icons.info_outline, color: {color}, size: {format_geometry_literal(icon_size)})"
        )
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
        and node.type in {NodeType.COLUMN, NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}
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
    shadows = ", ".join(_shadow_expr(effect) for effect in style.effects if effect.kind == "drop")
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
            f"ClipRRect(borderRadius: BorderRadius.circular({node.style.border_radius}), child: "
        )
    else:
        clip_open = "ClipRect(child: "
    fill_color = (
        dart_color_expr(node.style)
        if node.style.background_color
        else "Theme.of(context).colorScheme.surface"
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
    return f"DecoratedBox(decoration: BoxDecoration(boxShadow: [{drop_shadows}]), child: {frosted})"


def _is_form_field_group_column(node: CleanDesignTreeNode) -> bool:
    """Return True for label + field stacks that must grow past a Figma bbox height."""
    if node.type != NodeType.COLUMN:
        return False
    child_types = {child.type for child in node.children}
    if NodeType.TEXT in child_types and NodeType.INPUT in child_types:
        return True
    if NodeType.TEXT in child_types and len(node.children) > 1:
        return any(
            child.type in {NodeType.INPUT, NodeType.BUTTON, NodeType.COLUMN, NodeType.ROW}
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


def _wrap_widget_with_box_decoration(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    responsive_enabled: bool = False,
    design_artboard_width: float | None = None,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Wrap flex hosts with Figma padding and frame fill/radius."""

    def _decorate(inner: str) -> str:
        return _decorate_widget_with_box_decoration(
            node,
            inner,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )

    return _hoist_flex_parent_data(_decorate, widget)


def _square_bounds_for_circle_decoration(
    width: float | None,
    height: float | None,
    decoration: str | None,
) -> tuple[float | None, float | None]:
    """Circle ``BoxDecoration`` hosts must be square for centered glyph optics."""
    if decoration is None or "shape: BoxShape.circle" not in decoration:
        return width, height
    if width is None or height is None:
        return width, height
    wf = float(width)
    hf = float(height)
    if wf <= 0.0 or hf <= 0.0:
        return width, height
    side = max(wf, hf)
    return side, side


def _decorate_widget_with_box_decoration(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    responsive_enabled: bool = False,
    design_artboard_width: float | None = None,
    parent_node: CleanDesignTreeNode | None = None,
    omit_backdrop_blur: bool = False,
) -> str:
    """Apply padding and painted bounds to a non-flex host expression."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        column_is_compact_nav_tab,
        compact_nav_tab_should_paint_background,
    )
    from figma_flutter_agent.generator.layout.responsive import (
        responsive_emit_width,
        responsive_host_width_literal,
    )

    widget = wrap_flex_auto_layout_padding(node, widget)
    omit_nav_fill = column_is_compact_nav_tab(node) and not compact_nav_tab_should_paint_background(
        node,
        parent_row=parent_node,
    )
    will_frost = _effective_backdrop_blur(node) is not None and not omit_backdrop_blur
    if looks_like_bottom_docked_sheet(node):
        fields: list[str] = []
        if node.style.background_color:
            fields.append(f"color: {dart_color_expr(node.style)}")
        if node.style.effects and _effective_backdrop_blur(node) is None:
            shadows = ", ".join(
                _shadow_expr(effect) for effect in node.style.effects if effect.kind == "drop"
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
            omit_shadows=will_frost,
            omit_fill=omit_nav_fill or will_frost,
        )
    if decoration is None:
        if will_frost:
            return _wrap_frosted_layer_blur(node, widget)
        return widget
    from figma_flutter_agent.generator.layout.flex_policy import (
        _flex_child_should_bind_fixed_height,
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
        height = None
    width, height = _square_bounds_for_circle_decoration(width, height, decoration)
    if responsive_enabled:
        width = responsive_emit_width(width)

    from figma_flutter_agent.generator.layout.navigation.host import (
        bottom_nav_host_should_stretch_horizontal,
    )

    stretch_horizontal = bottom_nav_host_should_stretch_horizontal(node)
    width_lit = "double.infinity" if stretch_horizontal else None
    if width_lit is None and width is not None and width > 0:
        width_lit = responsive_host_width_literal(
            width,
            width_mode=node.sizing.width_mode,
        )

    foreground = box_foreground_decoration_expr(node.style)
    height_lit = (
        format_geometry_literal(float(height)) if height is not None and height > 0 else None
    )
    if width_lit is not None and height_lit is not None:
        if foreground is not None:
            wrapped = (
                f"Container(width: {width_lit}, height: {height_lit}, decoration: {decoration}, "
                f"foregroundDecoration: {foreground}, child: {widget})"
            )
        else:
            wrapped = (
                f"Container(width: {width_lit}, height: {height_lit}, decoration: {decoration}, "
                f"child: {widget})"
            )
    elif width_lit is not None:
        if foreground is not None:
            wrapped = (
                f"Container(width: {width_lit}, decoration: {decoration}, "
                f"foregroundDecoration: {foreground}, child: {widget})"
            )
        else:
            wrapped = f"Container(width: {width_lit}, decoration: {decoration}, child: {widget})"
    elif height is not None and height > 0:
        if foreground is not None:
            wrapped = (
                f"Container(height: {height}, decoration: {decoration}, "
                f"foregroundDecoration: {foreground}, child: {widget})"
            )
        else:
            wrapped = f"Container(height: {height}, decoration: {decoration}, child: {widget})"
    elif foreground is not None:
        wrapped = (
            f"Container(decoration: {decoration}, foregroundDecoration: {foreground}, "
            f"child: {widget})"
        )
    else:
        wrapped = f"Container(decoration: {decoration}, child: {widget})"
    if _effective_backdrop_blur(node) is not None and not omit_backdrop_blur:
        return _wrap_frosted_layer_blur(node, wrapped)
    from figma_flutter_agent.generator.layout.style.decoration import (
        border_radius_expr,
        inner_shadow_overlay_exprs,
        wrap_with_inner_shadow_overlays,
    )

    overlays = inner_shadow_overlay_exprs(
        node.style,
        frame_width=node.sizing.width,
        frame_height=node.sizing.height,
    )
    if overlays:
        radius = border_radius_expr(
            node.style,
            frame_width=node.sizing.width,
            frame_height=node.sizing.height,
        )
        wrapped = wrap_with_inner_shadow_overlays(
            wrapped,
            overlays,
            border_radius_expr=radius,
        )
    return wrapped
