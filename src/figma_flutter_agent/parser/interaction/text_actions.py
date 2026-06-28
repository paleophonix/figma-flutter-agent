"""Structural predicates for inline accent action text."""

from __future__ import annotations

import re

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

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


def layout_fact_static_screen_heading_text(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Return True for large centered headline copy that must stay non-interactive."""
    if node.type != NodeType.TEXT or parent_node is None:
        return False
    if parent_node.type != NodeType.COLUMN:
        return False
    font_size = node.style.font_size
    if font_size is None or float(font_size) < 20.0:
        return False
    if (node.style.text_align or "").upper() != "CENTER":
        return False
    weight = (node.style.font_weight or "").lower()
    is_bold = weight in {"w700", "bold", "700"} or (
        weight.startswith("w") and weight[1:].isdigit() and int(weight[1:]) >= 600
    )
    if not is_bold and float(font_size) < 24.0:
        return False
    parent_main = (parent_node.alignment.main or "start").lower()
    parent_cross = (parent_node.alignment.cross or "start").lower()
    if parent_main != "center" and parent_cross != "center":
        return False
    label = (node.text or "").strip()
    if not label or len(label) > 48:
        return False
    if node.sizing.width_mode == SizingMode.FILL:
        return True
    width = node.sizing.width
    parent_width = parent_node.sizing.width
    if width is None or parent_width is None:
        return float(font_size) >= 24.0
    return float(width) >= float(parent_width) * 0.6


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


def _primary_cta_painted_shell_height_ok(height: float | None) -> bool:
    if height is None:
        return False
    return 40.0 <= float(height) <= 64.0


def _primary_cta_painted_shell_style(node: CleanDesignTreeNode) -> bool:
    if node.style.gradient is not None:
        return True
    channels = _argb_rgb_channels(node.style.background_color)
    if channels is None:
        return False
    red, green, blue = channels
    return blue >= 120 and red <= 140 and green <= 160


def layout_fact_primary_cta_painted_row_shell(node: CleanDesignTreeNode) -> bool:
    """Return True when a painted ROW is a primary CTA host (full-surface tap target)."""
    if node.type != NodeType.ROW:
        return False
    if not _primary_cta_painted_shell_height_ok(node.sizing.height):
        return False
    if not _primary_cta_painted_shell_style(node):
        return False
    text_children = [child for child in node.children if child.type == NodeType.TEXT]
    if len(text_children) != 1:
        return False
    label = (text_children[0].text or "").strip()
    return bool(label) and len(label) <= 32


def layout_fact_primary_cta_label_in_painted_shell(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Return True when short CTA copy sits inside a painted primary button shell."""
    if node.type != NodeType.TEXT or parent_node is None:
        return False
    if parent_node.type not in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER}:
        return False
    if layout_fact_primary_cta_painted_row_shell(parent_node):
        return False
    label = (node.text or "").strip()
    if not label or len(label) > 32:
        return False
    if not _primary_cta_painted_shell_height_ok(parent_node.sizing.height):
        return False
    return _primary_cta_painted_shell_style(parent_node)


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
