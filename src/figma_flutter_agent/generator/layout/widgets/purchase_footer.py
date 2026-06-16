"""Flow-layout emitters for product purchase footer bands inside scroll sections."""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def stack_should_flow_as_purchase_footer_band(
    stack: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
    is_layout_root: bool,
) -> bool:
    """Return True when purchase chrome should reflow inside a sectionized column."""
    from figma_flutter_agent.parser.interaction.product import (
        layout_fact_stack_product_purchase_footer_panel,
    )

    if is_layout_root or parent_type != NodeType.COLUMN:
        return False
    return layout_fact_stack_product_purchase_footer_panel(stack)


def _child_is_full_bleed_backdrop(child: CleanDesignTreeNode, stack: CleanDesignTreeNode) -> bool:
    """Return True when a stack child paints the full-width footer panel background."""
    stack_width = stack.sizing.width
    if stack_width is None or float(stack_width) <= 0:
        return False
    placement = child.stack_placement
    child_width = placement.width if placement is not None and placement.width is not None else None
    if child_width is None:
        child_width = child.sizing.width
    if child_width is None or float(child_width) <= 0:
        return False
    left = placement.left if placement is not None and placement.left is not None else 0.0
    return float(child_width) >= float(stack_width) * 0.85 and float(left) <= float(stack_width) * 0.05


def _child_flow_ordinal(child: CleanDesignTreeNode) -> tuple[float, float]:
    """Return top-then-left ordering for footer chrome children."""
    placement = child.stack_placement
    top = float(placement.top) if placement is not None and placement.top is not None else 0.0
    left = float(placement.left) if placement is not None and placement.left is not None else 0.0
    return top, left


def _child_right_edge(child: CleanDesignTreeNode) -> float:
    """Return the right edge of a footer chrome child from placement or sizing."""
    placement = child.stack_placement
    left = float(placement.left) if placement is not None and placement.left is not None else 0.0
    width = placement.width if placement is not None and placement.width is not None else None
    if width is None:
        width = child.sizing.width
    if width is None:
        return left
    return left + float(width)


def emit_purchase_footer_flow_layout(
    node: CleanDesignTreeNode,
    ordered_pairs: list[tuple[CleanDesignTreeNode, str]],
) -> str:
    """Emit purchase footer chrome as overlay Row flow instead of absolute coordinates."""
    stack_width = float(node.sizing.width or 0.0)
    stack_height = float(node.sizing.height or 0.0)
    backdrop_pairs = [
        pair for pair in ordered_pairs if _child_is_full_bleed_backdrop(pair[0], node)
    ]
    chrome_pairs = [
        pair for pair in ordered_pairs if not _child_is_full_bleed_backdrop(pair[0], node)
    ]
    chrome_pairs.sort(key=lambda pair: _child_flow_ordinal(pair[0]))

    backdrop_body = ", ".join(widget for _, widget in backdrop_pairs) or "const SizedBox.shrink()"
    if not chrome_pairs:
        height_lit = format_geometry_literal(stack_height) if stack_height > 0 else None
        if height_lit is not None:
            return f"SizedBox(height: {height_lit}, child: {backdrop_body})"
        return backdrop_body

    tops = [_child_flow_ordinal(child)[0] for child, _ in chrome_pairs]
    lefts = [_child_flow_ordinal(child)[1] for child, _ in chrome_pairs]
    rights = [_child_right_edge(child) for child, _ in chrome_pairs]
    pad_top = max(0.0, min(tops))
    pad_left = max(0.0, min(lefts))
    pad_right = max(0.0, stack_width - max(rights)) if stack_width > 0 else 0.0

    row_parts: list[str] = []
    for index, (_, widget) in enumerate(chrome_pairs):
        if index > 0:
            previous_child = chrome_pairs[index - 1][0]
            current_child = chrome_pairs[index][0]
            gap = _child_flow_ordinal(current_child)[1] - _child_right_edge(previous_child)
            if gap > 4.0:
                row_parts.append("const Spacer()")
            elif gap > 0.5:
                row_parts.append(f"SizedBox(width: {format_geometry_literal(gap)})")
        row_parts.append(widget)

    row_body = ", ".join(row_parts)
    chrome_row = (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [{row_body}]"
        ")"
    )
    pad_top_lit = format_geometry_literal(pad_top)
    pad_left_lit = format_geometry_literal(pad_left)
    pad_right_lit = format_geometry_literal(pad_right)
    overlay = (
        "Padding("
        f"padding: EdgeInsets.only(top: {pad_top_lit}, left: {pad_left_lit}, right: {pad_right_lit}), "
        f"child: {chrome_row}"
        ")"
    )

    if backdrop_pairs:
        height_lit = format_geometry_literal(stack_height) if stack_height > 0 else None
        sized_backdrop = (
            f"SizedBox(width: double.infinity, height: {height_lit}, child: {backdrop_body})"
            if height_lit is not None
            else f"SizedBox(width: double.infinity, child: {backdrop_body})"
        )
        return (
            "Stack("
            "clipBehavior: Clip.none, "
            "alignment: Alignment.topLeft, "
            f"children: [{sized_backdrop}, {overlay}]"
            ")"
        )
    return overlay
