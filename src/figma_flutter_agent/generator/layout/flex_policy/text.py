"""Text-specific predicates for flex policy."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode


def text_in_card_metadata_rail(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
    *,
    parent_type: NodeType | None = None,
) -> bool:
    """True when copy sits in the narrow right-hand metadata rail of a list card."""
    from figma_flutter_agent.generator.layout.flex_policy.column import column_is_card_metadata_slot
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        _CARD_METADATA_STACK_MAX_WIDTH,
        row_is_card_composite_body,
        row_is_status_pill_badge,
    )

    if node.type != NodeType.TEXT or parent_node is None:
        return False
    from figma_flutter_agent.parser.interaction import (
        _subtree_has_currency_price,
        stack_is_category_component_tile,
    )

    if stack_is_category_component_tile(parent_node):
        return False
    if parent_type == NodeType.COLUMN and _subtree_has_currency_price(parent_node):
        return False
    if row_is_status_pill_badge(parent_node):
        return False
    if parent_type == NodeType.COLUMN and column_is_card_metadata_slot(parent_node):
        return True
    if parent_type == NodeType.ROW and row_is_card_composite_body(parent_node):
        child_width = float(node.sizing.width or 0.0)
        return 0 < child_width <= _CARD_METADATA_STACK_MAX_WIDTH
    if parent_node.type == NodeType.STACK:
        width = parent_node.sizing.width
        return width is not None and 0 < width <= _CARD_METADATA_STACK_MAX_WIDTH
    return False


def text_is_geometry_multiline(node: CleanDesignTreeNode) -> bool:
    """Return True when Figma box metrics imply soft-wrapped multiline text."""
    if node.type != NodeType.TEXT:
        return False
    raw = (node.text or "").strip()
    if not raw:
        return False
    if "\n" in raw or len(raw.splitlines()) > 1:
        return True
    text_height = node.sizing.height
    font_size = node.style.font_size
    if text_height is None or font_size is None or font_size <= 0:
        return False
    metrics = node.text_metrics_frame
    if metrics is not None and metrics.line_height_px and metrics.line_height_px > 0:
        if float(text_height) / float(metrics.line_height_px) >= 1.8:
            return True
    glyph_height = node.style.glyph_height
    if glyph_height is not None and float(glyph_height) > float(font_size) * 1.45:
        return True
    return float(text_height) > float(font_size) * 1.6


def geometry_multiline_max_lines(node: CleanDesignTreeNode) -> int:
    """Estimate wrapped line count from Figma text box metrics."""
    text_height = node.sizing.height
    font_size = node.style.font_size or 16.0
    if text_height is None or text_height <= 0:
        return 2
    metrics = node.text_metrics_frame
    if metrics is not None and metrics.line_height_px and metrics.line_height_px > 0:
        return max(2, int(round(float(text_height) / float(metrics.line_height_px))))
    return max(2, int(round(float(text_height) / (float(font_size) * 1.3))))


def _text_has_multiple_lines(node: CleanDesignTreeNode) -> bool:
    """Return True when Figma text content spans more than one line."""
    return text_is_geometry_multiline(node)


def text_preserves_intrinsic_wrap_width(node: CleanDesignTreeNode) -> bool:
    """True when soft-wrapped text must keep its Figma frame width under stretch."""
    if node.type != NodeType.TEXT:
        return False
    if not text_is_geometry_multiline(node):
        return False
    width = node.sizing.width
    if width is None or width <= 0:
        return False
    return node.sizing.width_mode != SizingMode.FILL


def _subtree_has_input(node: CleanDesignTreeNode) -> bool:
    """Return True when an ``INPUT`` appears anywhere under ``node``."""
    if node.type == NodeType.INPUT:
        return True
    return any(_subtree_has_input(child) for child in node.children)
