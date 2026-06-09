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

    pill_shell = next(
        (
            child
            for child in node.children
            if child.type in {NodeType.CONTAINER, NodeType.ROW, NodeType.COLUMN}
            and child.style.border_radius is not None
            and float(child.style.border_radius) >= 12.0
        ),
        None,
    )
    radius_lit = (
        format_geometry_literal(float(pill_shell.style.border_radius))
        if pill_shell is not None and pill_shell.style.border_radius is not None
        else "32.0"
    )
    from figma_flutter_agent.generator.layout.style import text_style_expr

    qty_node = _quantity_text_node(node)
    accent = "AppColors.primary"
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
    return (
        "Material("
        "color: Color(0xFFFFFFFF), "
        "elevation: 3, "
        f"borderRadius: BorderRadius.circular({radius_lit}), "
        "clipBehavior: Clip.antiAlias, "
        "child: Padding("
        f"padding: EdgeInsets.symmetric(horizontal: {pad_h_lit}, vertical: {pad_h_lit}), "
        f"child: {row}"
        ")"
        ")"
    )
