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


def price_or_value_label_fact(text: str | None) -> bool:
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
    if price_or_value_label_fact(label):
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


def _neutral_secondary_cta_painted_shell_style(node: CleanDesignTreeNode) -> bool:
    """Return True for dark neutral filled secondary CTA shells (e.g. ``0xFF3A3A3C``)."""
    if node.style.gradient is not None:
        return False
    channels = _argb_rgb_channels(node.style.background_color)
    if channels is None:
        return False
    red, green, blue = channels
    if max(red, green, blue) > 100 or min(red, green, blue) < 28:
        return False
    spread = max(red, green, blue) - min(red, green, blue)
    return spread <= 16


def _painted_cta_shell_style(node: CleanDesignTreeNode) -> bool:
    return _primary_cta_painted_shell_style(node) or _neutral_secondary_cta_painted_shell_style(
        node
    )


def _painted_cta_shell_label(node: CleanDesignTreeNode) -> str | None:
    """Return short CTA label text when ``node`` is a painted action shell."""
    text_children = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]
    if len(text_children) == 1:
        return (text_children[0].text or "").strip()
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    text_nodes = [
        item
        for item in _descendant_nodes(node, 4)
        if item.type == NodeType.TEXT and (item.text or "").strip()
    ]
    if len(text_nodes) != 1:
        return None
    return (text_nodes[0].text or "").strip()


def layout_fact_painted_cta_action_shell(node: CleanDesignTreeNode) -> bool:
    """Return True when a painted shell is a full-surface CTA tap host."""
    if node.type not in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER, NodeType.STACK}:
        return False
    if not _primary_cta_painted_shell_height_ok(node.sizing.height):
        return False
    if not _painted_cta_shell_style(node):
        return False
    label = _painted_cta_shell_label(node)
    return bool(label) and len(label) <= 32


def layout_fact_primary_cta_painted_row_shell(node: CleanDesignTreeNode) -> bool:
    """Return True when a painted ROW is a primary CTA host (full-surface tap target)."""
    return node.type == NodeType.ROW and layout_fact_painted_cta_action_shell(node)


def layout_fact_narrow_centered_figma_single_line_title(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Return True when centered title must stay single-line in a narrow header column."""
    if node.type != NodeType.TEXT or parent_node is None:
        return False
    if parent_node.type != NodeType.COLUMN:
        return False
    if (node.style.text_align or "").upper() != "CENTER":
        return False
    parent_width = parent_node.sizing.width
    if parent_width is None or float(parent_width) > 200.0:
        return False
    font_size = node.style.font_size
    text_height = node.sizing.height
    if font_size is None or text_height is None:
        return False
    line_height = node.style.line_height or float(font_size) * 1.27
    if float(text_height) > float(line_height) * 1.3:
        return False
    label = (node.text or "").strip()
    return len(label) >= 8


def layout_fact_primary_cta_label_in_painted_shell(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Return True when short CTA copy sits inside a painted primary button shell."""
    if node.type != NodeType.TEXT or parent_node is None:
        return False
    if parent_node.type not in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER}:
        return False
    if layout_fact_painted_cta_action_shell(parent_node):
        return False
    label = (node.text or "").strip()
    if not label or len(label) > 32:
        return False
    if not _primary_cta_painted_shell_height_ok(parent_node.sizing.height):
        return False
    return _painted_cta_shell_style(parent_node)


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
