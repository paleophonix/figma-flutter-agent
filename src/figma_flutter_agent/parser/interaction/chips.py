"""Chip and picker predicates (weekday chips, time wheel)."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .shared import (
    _MAX_LOCAL_DEPTH,
    _WEEKDAY_CHIP_LABELS,
    _WEEKDAY_CHIP_MAX_SIZE,
    _WEEKDAY_CHIP_MIN_SIZE,
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


def looks_like_weekday_chip_stack(node: CleanDesignTreeNode) -> bool:
    """Return True for circular single-letter weekday selectors in a chip row."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (_WEEKDAY_CHIP_MIN_SIZE <= float(width) <= _WEEKDAY_CHIP_MAX_SIZE):
        return False
    if not (_WEEKDAY_CHIP_MIN_SIZE <= float(height) <= _WEEKDAY_CHIP_MAX_SIZE):
        return False
    text_nodes = [item for item in _local_nodes(node, _MAX_LOCAL_DEPTH) if item.type == NodeType.TEXT]
    if len(text_nodes) != 1 or not text_nodes[0].text:
        return False
    label = text_nodes[0].text.strip().lower()
    return label in _WEEKDAY_CHIP_LABELS


def weekday_chip_label(node: CleanDesignTreeNode) -> str:
    """Return the weekday abbreviation shown on a chip stack."""
    for item in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if item.type == NodeType.TEXT and item.text:
            return item.text.strip().upper()
    return ""


def weekday_chip_initially_selected(node: CleanDesignTreeNode) -> bool:
    """Infer selected state from dark fill on the chip surface."""
    for item in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if item.type not in {NodeType.CONTAINER, NodeType.VECTOR}:
            continue
        color = item.style.background_color
        if color is not None and "3F414E" in color.upper():
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
