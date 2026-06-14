"""Figma component chip variant axes (Text#, Style) for choice chips."""

from __future__ import annotations

import re

from figma_flutter_agent.parser.text_case import apply_figma_text_case
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.schemas.style import FigmaTextCase

from .shared import _descendant_nodes, _local_nodes

_TEXT_VARIANT_AXIS = re.compile(r"^Text#", re.IGNORECASE)
_CHIP_SELECTED_STYLE_VALUES = frozenset({"focus", "selected", "on"})


def chip_component_label(node: CleanDesignTreeNode) -> str:
    """Return the label from the first ``Text#`` variant property axis."""
    if node.variant is None:
        return ""
    for key, value in node.variant.variant_properties.items():
        if _TEXT_VARIANT_AXIS.match(key):
            trimmed = (value or "").strip()
            if trimmed:
                return trimmed
    return ""


def chip_component_text_case(node: CleanDesignTreeNode) -> FigmaTextCase | None:
    """Return ``textCase`` from a nested TEXT child when still present."""
    for item in _descendant_nodes(node, 4):
        if item.type == NodeType.TEXT and item.style.text_case:
            return item.style.text_case
    return None


def chip_component_display_label(node: CleanDesignTreeNode) -> str:
    """Return visible chip copy with Figma ``textCase`` applied."""
    raw = chip_component_label(node)
    if not raw:
        for item in _local_nodes(node, 3):
            if item.type == NodeType.TEXT and (item.text or "").strip():
                raw = item.text.strip()
                return apply_figma_text_case(raw, item.style.text_case)
        return ""
    text_case = chip_component_text_case(node) or node.style.text_case
    return apply_figma_text_case(raw, text_case)


def capture_chip_prune_facts(node: CleanDesignTreeNode) -> None:
    """Copy nested TEXT ``textCase`` onto the chip row before duplicate pruning."""
    if not is_tag_component_chip_row(node):
        return
    text_case = chip_component_text_case(node)
    if text_case is None:
        return
    node.style = node.style.model_copy(update={"text_case": text_case})


def chip_component_selected(node: CleanDesignTreeNode) -> bool:
    """Return True when the chip variant axis marks a selected/focus state."""
    if node.variant is None:
        return False
    props = node.variant.variant_properties
    for axis in ("Style", "State"):
        raw = props.get(axis)
        if raw and raw.strip().lower() in _CHIP_SELECTED_STYLE_VALUES:
            return True
    for item in _local_nodes(node, 3):
        if item.type not in {NodeType.CONTAINER, NodeType.ROW, NodeType.COLUMN}:
            continue
        color = item.style.background_color
        if color is not None and color.upper() not in {"#FFFFFFFF", "#FFFFFF", "FFFFFFFF"}:
            if item.style.background_color and "3F414E" in color.upper():
                return True
    return False


def is_tag_component_chip_row(node: CleanDesignTreeNode) -> bool:
    """Return True for Figma ``Tag`` component instance rows used as choice chips."""
    if node.type != NodeType.ROW:
        return False
    if node.name.strip().lower() != "tag":
        return False
    if chip_component_label(node):
        return True
    if node.variant is not None and any(
        _TEXT_VARIANT_AXIS.match(key) for key in node.variant.variant_properties
    ):
        return True
    return node.cluster_id is not None
