"""Input and form field inspection utilities for Figma interactive nodes."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .predicates import (
    _INPUT_TRAILING_ICON_DESCENDANT_DEPTH,
    _MAX_LOCAL_DEPTH,
    _descendant_nodes,
    _local_nodes,
    _stack_has_vector_icon,
    looks_like_input_trailing_icon_button,
)


def textarea_hint_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """First non-empty ``TEXT`` descendant for a textarea shell."""

    def first_text(item: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if item.type == NodeType.TEXT and (item.text or "").strip():
            return item
        for child in item.children:
            found = first_text(child)
            if found is not None:
                return found
        return None

    return first_text(node)


def input_hint_text(node: CleanDesignTreeNode) -> str:
    """Return placeholder label for an input-like stack group."""
    hint_node = input_hint_node(node)
    if hint_node is not None and hint_node.text:
        return hint_node.text.strip()
    return node.accessibility_label or node.name


def input_hint_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the placeholder ``TEXT`` node inside an input-like stack group."""
    for text_node in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if text_node.type == NodeType.TEXT and text_node.text:
            return text_node
    return None


def primary_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Pick the main RECTANGLE surface inside a group (largest area)."""
    surfaces = [
        n
        for n in _local_nodes(node, _MAX_LOCAL_DEPTH)
        if n.type == NodeType.CONTAINER
        and n.sizing.width
        and n.sizing.height
        and (n.style.background_color or n.style.border_color)
    ]
    if not surfaces:
        return None
    return max(surfaces, key=lambda n: float(n.sizing.width or 0) * float(n.sizing.height or 0))


def input_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Resolve painted surface for flex/stack ``INPUT`` frames.

    Figma often applies fill and corner radius on the ``INPUT`` host rather than a
    child ``CONTAINER``. Falls back to the host when it carries field chrome.
    """
    surface = primary_surface_node(node)
    if surface is not None:
        return surface
    if node.type == NodeType.INPUT and (
        node.style.background_color is not None or node.style.border_radius is not None
    ):
        return node
    return None


def input_value_style_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the prefilled value ``TEXT`` node inside a flex ``INPUT`` host."""
    chrome_ids = {id(item) for item in input_trailing_chrome_nodes(node)}
    hint = input_hint_node(node)
    hint_id = id(hint) if hint is not None else None
    candidates: list[CleanDesignTreeNode] = []

    def walk(children: list[CleanDesignTreeNode], skip: bool) -> None:
        for child in children:
            child_skip = skip or id(child) in chrome_ids
            if (
                child.type == NodeType.TEXT
                and not child_skip
                and child.text
                and id(child) != hint_id
            ):
                candidates.append(child)
            if child.children:
                walk(child.children, child_skip)

    walk(node.children, False)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: len((item.text or "").strip()),
    )


def input_flex_value_text(node: CleanDesignTreeNode) -> str | None:
    """Concatenate value ``TEXT`` leaves inside a flex ``INPUT``, excluding icon chrome."""
    chrome_ids = {id(item) for item in input_trailing_chrome_nodes(node)}
    parts: list[str] = []

    def walk(children: list[CleanDesignTreeNode], skip: bool) -> None:
        for child in children:
            child_skip = skip or id(child) in chrome_ids
            if child.type == NodeType.TEXT and not child_skip and child.text:
                parts.append(child.text.strip())
            if child.children:
                walk(child.children, child_skip)

    walk(node.children, False)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return "".join(parts)


def input_trailing_chrome_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Return icon/vector subtrees that sit beside the value inside a flex ``INPUT``."""

    def collect(children: list[CleanDesignTreeNode]) -> None:
        for child in children:
            if child.type == NodeType.BUTTON and looks_like_input_trailing_icon_button(child):
                chrome.append(child)
            elif child.type == NodeType.STACK and _stack_has_vector_icon(
                _descendant_nodes(child, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
            ):
                chrome.append(child)
            elif child.type == NodeType.VECTOR and (
                child.vector_asset_key or child.style.has_stroke
            ):
                chrome.append(child)
            elif child.type in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER}:
                collect(child.children)

    chrome: list[CleanDesignTreeNode] = []
    collect(node.children)
    return chrome
