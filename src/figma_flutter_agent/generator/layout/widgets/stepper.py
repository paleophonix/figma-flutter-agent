"""Compact product-card quantity stepper emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.parser.interaction import extract_cart_quantity_digit
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
    compact = (
        height is not None and float(height) <= _COMPACT_STEPPER_HOST_HEIGHT
    ) or (
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


def render_compact_quantity_stepper_stack(
    node: CleanDesignTreeNode,
    *,
    text_scaler_expr: str = "textScaler",
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
    accent = "Theme.of(context).colorScheme.primary"
    for child in node.children:
        if child.type == NodeType.VECTOR and child.style.background_color:
            accent = dart_color_expr(
                child.style,
                fallback="Theme.of(context).colorScheme.primary",
            )
            break
    qty_style = (
        text_style_expr(qty_node)
        if qty_node is not None
        else "Theme.of(context).textTheme.bodyMedium"
    )
    minus_zone = inline_custom_code_comment(
        custom_code_zone_id(node.id, "stepper-decrease")
    )
    plus_zone = inline_custom_code_comment(
        custom_code_zone_id(node.id, "stepper-increase")
    )
    tap_extent, icon_size, gap, pad_h = _compact_stepper_profile(node)
    tap_lit = format_geometry_literal(tap_extent)
    icon_lit = format_geometry_literal(icon_size)
    gap_lit = format_geometry_literal(gap)
    pad_h_lit = format_geometry_literal(pad_h)
    tap_target = (
        f"SizedBox(width: {tap_lit}, height: {tap_lit}, child: Center(child: ICON))"
    )
    minus = tap_target.replace(
        "ICON",
        f"Icon(Icons.remove, size: {icon_lit}, color: {accent})",
    )
    plus = tap_target.replace(
        "ICON",
        f"Icon(Icons.add, size: {icon_lit}, color: {accent})",
    )
    minus_control = (
        "InkWell("
        f"onTap: () {{ {minus_zone} }}, "
        "customBorder: const CircleBorder(), "
        f"child: {minus}"
        ")"
    )
    plus_control = (
        "InkWell("
        f"onTap: () {{ {plus_zone} }}, "
        "customBorder: const CircleBorder(), "
        f"child: {plus}"
        ")"
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
