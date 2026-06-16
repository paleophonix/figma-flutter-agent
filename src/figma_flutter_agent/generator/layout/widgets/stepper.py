"""Compact product-card quantity stepper emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.parser.interaction import extract_cart_quantity_digit
from figma_flutter_agent.parser.interaction.shared import _descendant_nodes
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_COMPACT_STEPPER_HOST_HEIGHT = 32.0
_COMPACT_STEPPER_HOST_WIDTH = 100.0
_STANDARD_TAP_EXTENT = 32.0
_COMPACT_TAP_EXTENT = 24.0
_STANDARD_ICON_SIZE = 16.0
_COMPACT_ICON_SIZE = 14.0
_STANDARD_GAP = 4.0
_COMPACT_GAP = 2.0
_STANDARD_PAD_H = 4.0
_COMPACT_PAD_H = 2.0
_PILL_SHELL_MIN_RADIUS = 12.0


def _vector_glyph_color_expr(vector: CleanDesignTreeNode, *, fallback: str) -> str | None:
    """Resolve painted glyph color from stroke or fill on a vector leaf."""
    from figma_flutter_agent.generator.layout.style import dart_color_expr

    style = vector.style
    if style.has_stroke and style.border_color:
        return dart_color_expr(
            style.model_copy(update={"background_color": style.border_color}),
            fallback=fallback,
        )
    if style.background_color:
        return dart_color_expr(style, fallback=fallback)
    return None


def _is_stepper_decorative_halo_vector(vector: CleanDesignTreeNode) -> bool:
    """Return True for low-opacity filled circles behind Material Icons, not stroke glyphs."""
    if vector.type != NodeType.VECTOR:
        return False
    style = vector.style
    if style.has_stroke and style.border_color:
        return False
    opacity = style.opacity
    return opacity is not None and opacity < 0.99


def _stepper_glyph_accent_color(node: CleanDesignTreeNode) -> str:
    """Return +/− icon color from Figma glyph paint (LAW-STEPPER-GLYPH-COLOR)."""
    fallback = "Theme.of(context).colorScheme.primary"
    for item in _descendant_nodes(node, 4):
        if item.type != NodeType.VECTOR or _is_stepper_decorative_halo_vector(item):
            continue
        if not item.style.has_stroke or not item.style.border_color:
            continue
        painted = _vector_glyph_color_expr(item, fallback=fallback)
        if painted is not None:
            return painted
    for item in _descendant_nodes(node, 4):
        if item.type != NodeType.VECTOR or _is_stepper_decorative_halo_vector(item):
            continue
        painted = _vector_glyph_color_expr(item, fallback=fallback)
        if painted is not None and painted != fallback:
            return painted
    for item in _descendant_nodes(node, 4):
        if item.type != NodeType.VECTOR or _is_stepper_decorative_halo_vector(item):
            continue
        painted = _vector_glyph_color_expr(item, fallback=fallback)
        if painted is not None:
            return painted
    return fallback


def _pill_shell_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the painted pill container inside a compact quantity stack."""
    for child in node.children:
        radius = child.style.border_radius
        if child.type in {NodeType.CONTAINER, NodeType.ROW, NodeType.COLUMN} and (
            radius is not None and float(radius) >= _PILL_SHELL_MIN_RADIUS
        ):
            return child
    return None


def compact_quantity_stepper_emit_width(node: CleanDesignTreeNode) -> float | None:
    """Return the compiled pill width — not the expanded Figma stack bbox."""
    shell = _pill_shell_node(node)
    if shell is not None:
        shell_width = shell.sizing.width
        if shell_width is not None and float(shell_width) > 0:
            return float(shell_width)
    tap_extent, _icon_size, gap, pad_h = _compact_stepper_profile(node)
    qty_node = _quantity_text_node(node)
    text_width = (
        float(qty_node.sizing.width)
        if qty_node is not None
        and qty_node.sizing.width is not None
        and float(qty_node.sizing.width) > 0
        else 10.0
    )
    return (pad_h * 2.0) + (tap_extent * 2.0) + (gap * 2.0) + text_width


def _compact_stepper_profile(node: CleanDesignTreeNode) -> tuple[float, float, float, float]:
    """Return tap extent, icon size, gap, and horizontal padding for a quantity pill."""
    width = node.sizing.width
    height = node.sizing.height
    compact = (height is not None and float(height) <= _COMPACT_STEPPER_HOST_HEIGHT) or (
        width is not None and float(width) > _COMPACT_STEPPER_HOST_WIDTH
    )
    if compact:
        return (
            _COMPACT_TAP_EXTENT,
            _COMPACT_ICON_SIZE,
            _COMPACT_GAP,
            _COMPACT_PAD_H,
        )
    return (
        _STANDARD_TAP_EXTENT,
        _STANDARD_ICON_SIZE,
        _STANDARD_GAP,
        _STANDARD_PAD_H,
    )


def _quantity_text_node(
    node: CleanDesignTreeNode,
    *,
    max_depth: int = 3,
) -> CleanDesignTreeNode | None:
    if max_depth < 0:
        return None
    if node.type == NodeType.TEXT:
        text = (node.text or "").strip()
        if text.isdigit() and 0 < len(text) <= 3:
            return node
    for child in node.children:
        found = _quantity_text_node(child, max_depth=max_depth - 1)
        if found is not None:
            return found
    return None


def _stepper_glyph_ordinal(node: CleanDesignTreeNode) -> float:
    """Return horizontal ordinal for ordering minus/plus stroke glyphs."""
    placement = node.stack_placement
    if placement is not None and placement.left is not None:
        return float(placement.left)
    return float(node.offset_x or 0.0)


def _stepper_stroke_glyph_leaf(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the stroke vector leaf inside a stepper control host."""
    for item in _descendant_nodes(node, 3):
        if item.type != NodeType.VECTOR or _is_stepper_decorative_halo_vector(item):
            continue
        if item.style.has_stroke or item.vector_asset_key:
            return item
    return None


def _is_stepper_solid_tap_disc(node: CleanDesignTreeNode) -> bool:
    """Filled circular tap target exported as a vector asset, not the +/- glyph."""
    if node.type != NodeType.VECTOR:
        return False
    style = node.style
    if style.has_stroke and style.border_color:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    extent_w = float(width)
    extent_h = float(height)
    if not (18.0 <= extent_w <= 28.0 and 18.0 <= extent_h <= 28.0):
        return False
    return abs(extent_w - extent_h) <= 2.0 and bool(style.background_color or node.vector_asset_key)


def _is_degenerate_axis_glyph(vector: CleanDesignTreeNode) -> bool:
    """Return True for stroke-only axis lines that cannot render as standalone glyphs."""
    if vector.type != NodeType.VECTOR:
        return False
    width = vector.sizing.width
    height = vector.sizing.height
    if width is None or height is None:
        return False
    return float(width) <= 1.0 or float(height) <= 1.0


def _stepper_glyph_asset_candidates(host: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Collect exported glyph assets inside a stepper control host."""
    candidates: list[CleanDesignTreeNode] = []
    seen: set[str] = set()

    def visit(node: CleanDesignTreeNode, depth: int) -> None:
        if node.id in seen or depth > 4:
            return
        seen.add(node.id)
        if node.vector_asset_key and not _is_stepper_decorative_halo_vector(node):
            if not _is_stepper_solid_tap_disc(node):
                candidates.append(node)
        elif node.type == NodeType.VECTOR and not _is_stepper_decorative_halo_vector(node):
            if not _is_degenerate_axis_glyph(node) and (
                node.style.has_stroke or node.vector_asset_key
            ):
                candidates.append(node)
        for child in node.children:
            visit(child, depth + 1)

    visit(host, 0)
    return candidates


def _stepper_glyph_asset_node(host: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return exported SVG asset node for a stepper control host (STACK or VECTOR)."""
    candidates = _stepper_glyph_asset_candidates(host)
    if candidates:

        def _glyph_area(node: CleanDesignTreeNode) -> float:
            width = float(node.sizing.width or 0.0)
            height = float(node.sizing.height or 0.0)
            if width <= 0.0 or height <= 0.0:
                return 9999.0
            return width * height

        return min(candidates, key=_glyph_area)
    if host.vector_asset_key and not _is_stepper_decorative_halo_vector(host):
        if not _is_stepper_solid_tap_disc(host):
            return host
    for item in _descendant_nodes(host, 3):
        if _is_stepper_decorative_halo_vector(item):
            continue
        if item.vector_asset_key and not _is_stepper_solid_tap_disc(item):
            return item
    return _stepper_stroke_glyph_leaf(host)


def _stepper_minus_plus_glyphs(
    node: CleanDesignTreeNode,
) -> tuple[CleanDesignTreeNode | None, CleanDesignTreeNode | None]:
    """Locate minus and plus glyphs from control hosts or flat vectors."""
    control_hosts = [
        child
        for child in node.children
        if child.type in {NodeType.STACK, NodeType.BUTTON}
        and _stepper_glyph_asset_node(child) is not None
    ]
    if len(control_hosts) >= 2:
        ordered = sorted(control_hosts, key=_stepper_glyph_ordinal)
        return (
            _stepper_glyph_asset_node(ordered[0]),
            _stepper_glyph_asset_node(ordered[-1]),
        )
    glyphs = [
        item
        for item in _descendant_nodes(node, 4)
        if item.type == NodeType.VECTOR
        and not _is_stepper_decorative_halo_vector(item)
        and (item.style.has_stroke or item.vector_asset_key)
    ]
    if len(glyphs) < 2:
        return None, None
    ordered = sorted(glyphs, key=_stepper_glyph_ordinal)
    return ordered[0], ordered[-1]


def _stepper_glyph_icon_widget(
    vector: CleanDesignTreeNode | None,
    *,
    uses_svg: bool,
    icon_lit: str,
    accent: str,
    material_icon: str,
) -> str:
    """Prefer exported Figma stroke SVG over Material Icons for stepper glyphs."""
    if vector is not None and uses_svg and vector.vector_asset_key:
        from figma_flutter_agent.generator.layout.common import escape_dart_string
        from figma_flutter_agent.generator.layout.widgets.svg import _render_svg_picture

        return _render_svg_picture(vector, escape_dart_string(vector.vector_asset_key))
    return f"Icon({material_icon}, size: {icon_lit}, color: {accent})"


def render_compact_quantity_stepper_stack(
    node: CleanDesignTreeNode,
    *,
    text_scaler_expr: str = "textScaler",
    uses_svg: bool = False,
) -> str | None:
    """Render a pill-shaped minus / quantity / plus row for overlapping Figma stacks."""
    quantity = extract_cart_quantity_digit(node)
    if quantity is None:
        return None

    pill_shell = _pill_shell_node(node)
    radius_lit = (
        format_geometry_literal(float(pill_shell.style.border_radius))
        if pill_shell is not None and pill_shell.style.border_radius is not None
        else "32.0"
    )
    from figma_flutter_agent.generator.layout.style import dart_color_expr, text_style_expr

    qty_node = _quantity_text_node(node)
    shell_color = (
        dart_color_expr(
            pill_shell.style,
            fallback="Theme.of(context).colorScheme.surface",
        )
        if pill_shell is not None
        else "Theme.of(context).colorScheme.surface"
    )
    accent = _stepper_glyph_accent_color(node)
    qty_style = (
        text_style_expr(qty_node)
        if qty_node is not None
        else "Theme.of(context).textTheme.bodyMedium"
    )
    minus_zone = inline_custom_code_comment(custom_code_zone_id(node.id, "stepper-decrease"))
    plus_zone = inline_custom_code_comment(custom_code_zone_id(node.id, "stepper-increase"))
    tap_extent, icon_size, gap, pad_h = _compact_stepper_profile(node)
    tap_lit = format_geometry_literal(tap_extent)
    icon_lit = format_geometry_literal(icon_size)
    gap_lit = format_geometry_literal(gap)
    pad_h_lit = format_geometry_literal(pad_h)
    minus_glyph, plus_glyph = _stepper_minus_plus_glyphs(node)
    minus_icon = _stepper_glyph_icon_widget(
        minus_glyph,
        uses_svg=uses_svg,
        icon_lit=icon_lit,
        accent=accent,
        material_icon="Icons.remove",
    )
    plus_icon = _stepper_glyph_icon_widget(
        plus_glyph,
        uses_svg=uses_svg,
        icon_lit=icon_lit,
        accent=accent,
        material_icon="Icons.add",
    )
    tap_target = f"SizedBox(width: {tap_lit}, height: {tap_lit}, child: Center(child: ICON))"
    minus = tap_target.replace("ICON", minus_icon)
    plus = tap_target.replace("ICON", plus_icon)
    minus_control = (
        f"InkWell(onTap: () {{ {minus_zone} }}, customBorder: const CircleBorder(), child: {minus})"
    )
    plus_control = (
        f"InkWell(onTap: () {{ {plus_zone} }}, customBorder: const CircleBorder(), child: {plus})"
    )
    row = (
        "Row("
        "mainAxisSize: MainAxisSize.min, "
        "mainAxisAlignment: MainAxisAlignment.center, "
        "crossAxisAlignment: CrossAxisAlignment.center, "
        "children: ["
        f"{minus_control}, "
        f"SizedBox(width: {gap_lit}), "
        f"Text('{quantity}', style: {qty_style}, textScaler: {text_scaler_expr}), "
        f"SizedBox(width: {gap_lit}), "
        f"{plus_control}"
        "]"
        ")"
    )
    pill = (
        "Material("
        f"color: {shell_color}, "
        "elevation: 3, "
        f"borderRadius: BorderRadius.circular({radius_lit}), "
        "clipBehavior: Clip.antiAlias, "
        "child: Padding("
        f"padding: EdgeInsets.symmetric(horizontal: {pad_h_lit}, vertical: {pad_h_lit}), "
        f"child: Center(child: {row})"
        ")"
        ")"
    )
    emit_width = compact_quantity_stepper_emit_width(node)
    if emit_width is None or emit_width <= 0:
        return pill
    width_lit = format_geometry_literal(emit_width)
    height = node.sizing.height
    if height is not None and float(height) > 0:
        height_lit = format_geometry_literal(float(height))
        return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {pill})"
    return f"SizedBox(width: {width_lit}, child: {pill})"
