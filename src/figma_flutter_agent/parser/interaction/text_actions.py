"""Structural predicates for inline accent action text."""

from __future__ import annotations

import re

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_PRICE_VALUE_RE = re.compile(r"^[\d\s.,₹$€£¥₴₸%+\-]+$")


def _argb_rgb_channels(color: str | None) -> tuple[int, int, int] | None:
    if not color:
        return None
    normalized = color.lower().removeprefix("0x").removeprefix("#")
    if len(normalized) == 8:
        normalized = normalized[2:]
    if len(normalized) != 6:
        return None
    try:
        value = int(normalized, 16)
    except ValueError:
        return None
    return (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF


def looks_like_price_or_value_label(text: str | None) -> bool:
    """Return True when copy is numeric price/discount value, not an action label."""
    if not text:
        return False
    label = text.strip()
    if not label:
        return False
    if _PRICE_VALUE_RE.fullmatch(label):
        return True
    return label.replace(",", "").replace(".", "").isdigit()


def layout_fact_actionable_accent_text_node(node: CleanDesignTreeNode) -> bool:
    """Return True for short accent-colored inline text that should stay tappable."""
    if node.type != NodeType.TEXT or not node.text:
        return False
    label = node.text.strip()
    if not label or len(label) > 40:
        return False
    if looks_like_price_or_value_label(label):
        return False
    if node.style.text_decoration == "underline":
        return True
    channels = _argb_rgb_channels(node.style.text_color)
    if channels is None:
        return False
    red, green, blue = channels
    if red < 160:
        return False
    if red <= green + 24 and red <= blue + 24:
        return False
    if green < 40 and blue < 40 and red > 200:
        return True
    return red > green + 40 and red > blue + 40


def layout_fact_primary_cta_label_in_painted_shell(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Return True when short CTA copy sits inside a painted primary button shell."""
    if node.type != NodeType.TEXT or parent_node is None:
        return False
    if parent_node.type not in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER}:
        return False
    label = (node.text or "").strip()
    if not label or len(label) > 32:
        return False
    height = parent_node.sizing.height
    if height is None or not (40.0 <= float(height) <= 64.0):
        return False
    if parent_node.style.gradient is not None:
        return True
    channels = _argb_rgb_channels(parent_node.style.background_color)
    if channels is None:
        return False
    red, green, blue = channels
    return blue >= 120 and red <= 140 and green <= 160


def subtree_has_actionable_accent_text(node: CleanDesignTreeNode, *, max_depth: int = 12) -> bool:
    """Return True when any descendant is accent inline action text."""
    if max_depth < 0:
        return False
    if layout_fact_actionable_accent_text_node(node):
        return True
    return any(
        subtree_has_actionable_accent_text(child, max_depth=max_depth - 1)
        for child in node.children
    )
