"""Layout facts for inline labeled input field component hosts."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .absolute_fields import (
    _SINGLE_LINE_FIELD_MAX_HEIGHT,
    _SINGLE_LINE_FIELD_MIN_HEIGHT,
)
from .input_fields import input_flex_value_text

_FIELD_LABEL_MAX_HEIGHT = 28.0


def _hosts_external_field_label(node: CleanDesignTreeNode) -> bool:
    """Return True when a sibling hosts a compact field label above the painted surface."""
    if node.type not in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER}:
        return False
    text_nodes: list[CleanDesignTreeNode] = []

    def walk(item: CleanDesignTreeNode) -> None:
        if item.type == NodeType.TEXT and (item.text or "").strip():
            text_nodes.append(item)
            return
        for child in item.children:
            walk(child)

    walk(node)
    if len(text_nodes) != 1:
        return False
    text_node = text_nodes[0]
    font_size = text_node.style.font_size
    if font_size is not None and float(font_size) > 14.0:
        return False
    height = node.sizing.height
    if height is not None and float(height) > _FIELD_LABEL_MAX_HEIGHT:
        return False
    return True


def layout_fact_flex_painted_input_surface(node: CleanDesignTreeNode) -> bool:
    """Return True for a flex-hug painted row/container that hosts a single value line."""
    if node.type not in {NodeType.ROW, NodeType.CONTAINER}:
        return False
    height = node.sizing.height
    if height is None:
        return False
    field_height = float(height)
    if not (_SINGLE_LINE_FIELD_MIN_HEIGHT <= field_height <= _SINGLE_LINE_FIELD_MAX_HEIGHT):
        return False
    has_chrome = bool(
        node.style.background_color is not None
        or node.style.border_color is not None
        or (node.style.border_width is not None and float(node.style.border_width) > 0)
        or (node.style.border_radius is not None and float(node.style.border_radius) > 0)
    )
    if not has_chrome:
        return False
    if input_flex_value_text(node) is None:
        return False
    return True


def layout_fact_inline_labeled_input_field_host(node: CleanDesignTreeNode) -> bool:
    """Return True for label + painted input-area columns emitted as one TextField."""
    if node.type != NodeType.COLUMN:
        return False
    if len(node.children) < 2:
        return False
    if layout_fact_phone_composite_field_host(node):
        return False
    surfaces = [child for child in node.children if layout_fact_flex_painted_input_surface(child)]
    if len(surfaces) != 1:
        return False
    labels = [
        child
        for child in node.children
        if child.id != surfaces[0].id and _hosts_external_field_label(child)
    ]
    return len(labels) == 1


def phone_composite_prefix_node(surface: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the country-prefix chrome row inside a phone composite surface."""
    for child in surface.children:
        if child.name and "country" in child.name.lower():
            return child
        if child.variant is not None and "countries" in (child.variant.component_name or "").lower():
            return child
        for descendant in child.children:
            if descendant.variant is not None and "countries" in (
                descendant.variant.component_name or ""
            ).lower():
                return child
    return None


def phone_composite_value_node(surface: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the editable phone body text node, excluding prefix chrome."""
    prefix = phone_composite_prefix_node(surface)
    prefix_ids = {prefix.id} if prefix is not None else set()
    candidates: list[CleanDesignTreeNode] = []

    def walk(item: CleanDesignTreeNode) -> None:
        if item.id in prefix_ids:
            return
        if item.type == NodeType.TEXT and (item.text or "").strip():
            candidates.append(item)
        for child in item.children:
            walk(child)

    walk(surface)
    if not candidates:
        return None
    return max(candidates, key=lambda item: len((item.text or "").strip()))


def layout_fact_phone_composite_input_surface(node: CleanDesignTreeNode) -> bool:
    """Return True when a painted input row hosts a country prefix and editable phone body."""
    if node.type not in {NodeType.ROW, NodeType.CONTAINER}:
        return False
    height = node.sizing.height
    if height is None:
        return False
    field_height = float(height)
    if not (_SINGLE_LINE_FIELD_MIN_HEIGHT <= field_height <= _SINGLE_LINE_FIELD_MAX_HEIGHT):
        return False
    has_chrome = bool(
        node.style.background_color is not None
        or node.style.border_color is not None
        or (node.style.border_width is not None and float(node.style.border_width) > 0)
    )
    if not has_chrome:
        return False
    if phone_composite_prefix_node(node) is None:
        return False
    return phone_composite_value_node(node) is not None


def layout_fact_phone_composite_field_host(node: CleanDesignTreeNode) -> bool:
    """Return True for label + phone-prefix composite columns."""
    if node.type != NodeType.COLUMN or len(node.children) < 2:
        return False
    surfaces = [
        child for child in node.children if layout_fact_phone_composite_input_surface(child)
    ]
    if len(surfaces) != 1:
        return False
    labels = [
        child
        for child in node.children
        if child.id != surfaces[0].id and _hosts_external_field_label(child)
    ]
    return len(labels) == 1


def layout_fact_phone_prefix_chrome_row(node: CleanDesignTreeNode) -> bool:
    """Return True when a row is country-prefix chrome inside a phone composite field."""
    if node.type != NodeType.ROW:
        return False
    if node.name and "country" in node.name.lower():
        return True
    for child in node.children:
        variant = child.variant
        if variant is not None and "countries" in (variant.component_name or "").lower():
            return True
        for descendant in child.children:
            descendant_variant = descendant.variant
            if descendant_variant is not None and "countries" in (
                descendant_variant.component_name or ""
            ).lower():
                return True
    return False


def coerce_inline_input_field_host(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Shape a labeled input column as an ``INPUT`` host for the shared field emitter."""
    surface = next(child for child in node.children if layout_fact_flex_painted_input_surface(child))
    label = next(
        child
        for child in node.children
        if child.id != surface.id and _hosts_external_field_label(child)
    )
    return node.model_copy(
        update={
            "type": NodeType.INPUT,
            "children": [label, surface],
        },
    )
