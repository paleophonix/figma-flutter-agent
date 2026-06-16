"""Flow-layout emitters for product purchase footer bands inside scroll sections."""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_FOOTER_Y_BAND_TOLERANCE = 8.0
_FULL_BLEED_CHILD_WIDTH_RATIO = 0.85


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


def _child_flow_width(child: CleanDesignTreeNode) -> float:
    """Return the horizontal span of a footer chrome child."""
    placement = child.stack_placement
    width = placement.width if placement is not None and placement.width is not None else None
    if width is None:
        width = child.sizing.width
    return float(width or 0.0)


def _group_chrome_pairs_by_y_band(
    chrome_pairs: list[tuple[CleanDesignTreeNode, str]],
    *,
    tolerance: float = _FOOTER_Y_BAND_TOLERANCE,
) -> list[list[tuple[CleanDesignTreeNode, str]]]:
    """Group footer chrome into horizontal bands by Figma top coordinate."""
    ordered = sorted(chrome_pairs, key=lambda pair: _child_flow_ordinal(pair[0]))
    bands: list[list[tuple[CleanDesignTreeNode, str]]] = []
    for pair in ordered:
        top = _child_flow_ordinal(pair[0])[0]
        if not bands:
            bands.append([pair])
            continue
        band_anchor_top = _child_flow_ordinal(bands[-1][-1][0])[0]
        if top - band_anchor_top > tolerance:
            bands.append([pair])
        else:
            bands[-1].append(pair)
    for band in bands:
        band.sort(key=lambda pair: _child_flow_ordinal(pair[0])[1])
    return bands


def _emit_chrome_band_row(
    band_pairs: list[tuple[CleanDesignTreeNode, str]],
    *,
    inner_width: float,
) -> str:
    """Emit one footer chrome row that fits the padded host width."""
    row_parts: list[str] = []
    for index, (child, widget) in enumerate(band_pairs):
        if index > 0:
            previous_child = band_pairs[index - 1][0]
            gap = _child_flow_ordinal(child)[1] - _child_right_edge(previous_child)
            if gap > 4.0:
                row_parts.append("const Spacer()")
            elif gap > 0.5:
                row_parts.append(f"SizedBox(width: {format_geometry_literal(gap)})")
        child_width = _child_flow_width(child)
        if (
            len(band_pairs) == 1
            and inner_width > 0.0
            and child_width >= inner_width * _FULL_BLEED_CHILD_WIDTH_RATIO
        ):
            row_parts.append(f"Expanded(child: {widget})")
        else:
            row_parts.append(widget)
    row_body = ", ".join(row_parts)
    return (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [{row_body}]"
        ")"
    )


def emit_purchase_footer_flow_layout(
    node: CleanDesignTreeNode,
    ordered_pairs: list[tuple[CleanDesignTreeNode, str]],
) -> str:
    """Emit purchase footer chrome as overlay flow instead of absolute coordinates."""
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
    inner_width = max(0.0, stack_width - pad_left - pad_right)

    bands = _group_chrome_pairs_by_y_band(chrome_pairs)
    band_rows = [
        _emit_chrome_band_row(band, inner_width=inner_width) for band in bands if band
    ]
    if len(band_rows) == 1:
        chrome_body = band_rows[0]
    else:
        chrome_body = (
            "Column("
            "mainAxisSize: MainAxisSize.min, "
            "crossAxisAlignment: CrossAxisAlignment.stretch, "
            f"children: [{', '.join(band_rows)}]"
            ")"
        )

    pad_top_lit = format_geometry_literal(pad_top)
    pad_left_lit = format_geometry_literal(pad_left)
    pad_right_lit = format_geometry_literal(pad_right)
    overlay = (
        "Padding("
        f"padding: EdgeInsets.only(top: {pad_top_lit}, left: {pad_left_lit}, right: {pad_right_lit}), "
        f"child: {chrome_body}"
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
