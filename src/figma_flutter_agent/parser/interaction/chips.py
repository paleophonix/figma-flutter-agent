"""Chip and picker predicates (weekday chips, time wheel)."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .shared import (
    _MAX_LOCAL_DEPTH,
    COMPACT_CHIP_ROW_ROLE,
    _descendant_nodes,
    _local_nodes,
)

_TIME_WHEEL_PICKER_MIN_TEXT_COUNT = 8
_TIME_WHEEL_PICKER_MIN_HEIGHT = 120.0
_TIME_WHEEL_PICKER_MIN_WIDTH = 250.0


def _wheel_picker_text_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    texts: list[CleanDesignTreeNode] = []
    for item in _descendant_nodes(node, 5):
        if item.type != NodeType.TEXT or not item.text:
            continue
        label = item.text.strip().upper()
        if label in {"AM", "PM"} or label.isdigit():
            texts.append(item)
    return texts


def is_compact_chip_row(node: CleanDesignTreeNode) -> bool:
    """Return True when a node is a reconciled compact chip choice row."""
    return node.layout_role == COMPACT_CHIP_ROW_ROLE


def looks_like_weekday_chip_stack(node: CleanDesignTreeNode) -> bool:
    """Return True for compact chip stacks (structural anatomy only)."""
    from figma_flutter_agent.parser.semantics.signals.chip_anatomy import (
        is_compact_chip_stack,
    )

    return is_compact_chip_stack(node)


def weekday_chip_label(node: CleanDesignTreeNode) -> str:
    """Return the weekday abbreviation shown on a chip stack."""
    for item in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if item.type == NodeType.TEXT and item.text:
            return item.text.strip().upper()
    return ""


def weekday_chip_initially_selected(node: CleanDesignTreeNode) -> bool:
    """Infer selected state from variant facts or dark painted surfaces."""
    from figma_flutter_agent.generator.layout.style.colors import is_dark_fill_color
    from figma_flutter_agent.generator.layout.style.facts import (
        selected_from_variant_or_luminance,
    )

    if selected_from_variant_or_luminance(node):
        return True
    for item in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if is_dark_fill_color(item.style.background_color):
            return True
    return False


def looks_like_wheel_time_picker_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when a stack subtree matches a scrollable hour/minute/period wheel."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if float(width) < _TIME_WHEEL_PICKER_MIN_WIDTH or float(height) < _TIME_WHEEL_PICKER_MIN_HEIGHT:
        return False
    wheel_texts = _wheel_picker_text_nodes(node)
    return len(wheel_texts) >= _TIME_WHEEL_PICKER_MIN_TEXT_COUNT
