"""Compact product-card quantity stepper emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.parser.interaction import extract_cart_quantity_digit
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


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
    tap_target = (
        "SizedBox(width: 32.0, height: 32.0, child: Center(child: ICON))"
    )
    minus = tap_target.replace("ICON", f"Icon(Icons.remove, size: 16, color: {accent})")
    plus = tap_target.replace("ICON", f"Icon(Icons.add, size: 16, color: {accent})")
    return (
        "Material("
        "elevation: 3, "
        f"borderRadius: BorderRadius.circular({radius_lit}), "
        "clipBehavior: Clip.antiAlias, "
        "child: Padding("
        "padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4), "
        "child: Row("
        "mainAxisSize: MainAxisSize.min, "
        "mainAxisAlignment: MainAxisAlignment.center, "
        "crossAxisAlignment: CrossAxisAlignment.center, "
        "children: ["
        "GestureDetector("
        "behavior: HitTestBehavior.opaque, "
        f"onTap: () {{ {minus_zone} }}, "
        f"child: {minus}"
        "), "
        "const SizedBox(width: 4), "
        f"Text('{quantity}', style: {qty_style}, textScaler: {text_scaler_expr}), "
        "const SizedBox(width: 4), "
        "GestureDetector("
        "behavior: HitTestBehavior.opaque, "
        f"onTap: () {{ {plus_zone} }}, "
        f"child: {plus}"
        ")"
        "]"
        ")"
        ")"
        ")"
    )
