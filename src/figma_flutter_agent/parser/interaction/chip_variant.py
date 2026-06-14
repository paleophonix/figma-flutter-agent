"""Figma component chip variant axes (Text#, Style) for choice chips."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.layout.style.colors import is_dark_fill_color
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
    return is_dark_fill_color(node.style.background_color)


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


def chip_component_label_text_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the nested TEXT node that renders chip copy, when present."""
    for item in _local_nodes(node, 4):
        if item.type == NodeType.TEXT:
            return item
    return None


def iter_cluster_tag_chips(
    trees: list[CleanDesignTreeNode],
    cluster_id: str,
) -> list[CleanDesignTreeNode]:
    """Collect tag chip rows that belong to a widget cluster."""
    found: list[CleanDesignTreeNode] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id == cluster_id and is_tag_component_chip_row(node):
            found.append(node)
        for child in node.children:
            walk(child)

    for tree in trees:
        walk(tree)
    return found


def chip_cluster_style_refs(
    trees: list[CleanDesignTreeNode] | None,
    cluster_id: str,
    representative: CleanDesignTreeNode,
) -> tuple[CleanDesignTreeNode | None, CleanDesignTreeNode | None]:
    """Return ``(unselected, selected)`` exemplars from a chip cluster when available."""
    unselected: CleanDesignTreeNode | None = None
    selected: CleanDesignTreeNode | None = None
    if trees:
        for node in iter_cluster_tag_chips(trees, cluster_id):
            if chip_component_selected(node):
                if selected is None:
                    selected = node
            elif unselected is None:
                unselected = node
            if unselected is not None and selected is not None:
                break
    if unselected is None and not chip_component_selected(representative):
        unselected = representative
    if selected is None and chip_component_selected(representative):
        selected = representative
    return unselected, selected


def chip_component_label_font_size(node: CleanDesignTreeNode) -> float | None:
    """Return recovered chip label size (text metrics first, then TEXT style)."""
    text_node = chip_component_label_text_node(node)
    if text_node is None:
        return None
    metrics = text_node.text_metrics_frame
    if metrics is not None and metrics.font_size is not None and float(metrics.font_size) > 0:
        return float(metrics.font_size)
    if text_node.style.font_size is not None and float(text_node.style.font_size) > 0:
        return float(text_node.style.font_size)
    return None
