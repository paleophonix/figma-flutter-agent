"""Input and form field inspection utilities for Figma interactive nodes."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .icons import (
    _stack_has_vector_icon,
    looks_like_input_trailing_icon_button,
)
from .shared import (
    _INPUT_HINTS,
    _INPUT_TRAILING_ICON_DESCENDANT_DEPTH,
    _MAX_LOCAL_DEPTH,
    _descendant_nodes,
    _label_matches_action_hint,
    _local_nodes,
)

_PASSWORD_DOT_CHARS = frozenset("•·●∙*·.")
_MAX_FIELD_LABEL_CHARS = 24
_FIELD_LABEL_MAX_FONT_SIZE = 14.0


def _node_contains_descendant(
    ancestor: CleanDesignTreeNode,
    target: CleanDesignTreeNode,
) -> bool:
    """Return True when ``target`` is nested under ``ancestor``."""
    if ancestor.id == target.id:
        return True
    return any(_node_contains_descendant(child, target) for child in ancestor.children)


def _nested_input_area_host(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the nested ``INPUT`` child that carries painted field chrome."""
    for child in node.children:
        if child.type == NodeType.INPUT:
            return child
        if child.type in {NodeType.ROW, NodeType.COLUMN, NodeType.STACK, NodeType.CONTAINER}:
            for grandchild in child.children:
                if grandchild.type == NodeType.INPUT:
                    return grandchild
    return None


def _text_reads_as_external_field_label(text_node: CleanDesignTreeNode) -> bool:
    """True for short caption copy above a bordered input surface (Email, Password)."""
    from .forms import is_link_text

    text = (text_node.text or text_node.name or "").strip()
    if not text or is_link_text(text):
        return False
    if len(text) > _MAX_FIELD_LABEL_CHARS:
        return False
    font_size = text_node.style.font_size
    if font_size is not None and float(font_size) > _FIELD_LABEL_MAX_FONT_SIZE:
        return False
    lowered = text.lower()
    if lowered in _INPUT_HINTS or lowered in {"input", "input field", "field"}:
        return True
    if _label_matches_action_hint(lowered):
        return False
    return "email" in lowered or lowered == "password"


def input_field_label_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return external caption ``TEXT`` above a compact flex ``INPUT`` field."""
    if node.type != NodeType.INPUT:
        return None
    nested = _nested_input_area_host(node)
    candidates: list[CleanDesignTreeNode] = []
    for child in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if child.type != NodeType.TEXT:
            continue
        if not _text_reads_as_external_field_label(child):
            continue
        if nested is not None and _node_contains_descendant(nested, child):
            continue
        candidates.append(child)
    if not candidates:
        for child in node.children:
            if child.type not in {NodeType.ROW, NodeType.COLUMN}:
                continue
            for text_node in child.children:
                if text_node.type == NodeType.TEXT and _text_reads_as_external_field_label(
                    text_node
                ):
                    return text_node
        return None
    return min(
        candidates,
        key=lambda item: float(item.stack_placement.top or 0)
        if item.stack_placement is not None
        else 0.0,
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
    nested = _nested_input_area_host(node)
    search_root = nested if nested is not None else node
    label = input_field_label_node(node)
    label_id = id(label) if label is not None else None
    for text_node in _local_nodes(search_root, _MAX_LOCAL_DEPTH):
        if text_node.type != NodeType.TEXT or not text_node.text:
            continue
        if id(text_node) == label_id:
            continue
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


def surface_covers_node(node: CleanDesignTreeNode, surface: CleanDesignTreeNode) -> bool:
    """True when ``surface`` spans most of ``node``'s own area (its background fill).

    A surface that only covers a small fraction of the host (e.g. an icon
    rail beside a separate text block) is sibling content, not the host's
    painted background, and must not be folded into the wrapper decoration.
    """
    node_width, node_height = node.sizing.width, node.sizing.height
    surface_width, surface_height = surface.sizing.width, surface.sizing.height
    if not (node_width and node_height and surface_width and surface_height):
        return True
    node_area = float(node_width) * float(node_height)
    if node_area <= 0:
        return True
    surface_area = float(surface_width) * float(surface_height)
    return surface_area / node_area >= 0.5


def input_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Resolve painted surface for flex/stack ``INPUT`` frames.

    Figma often applies fill and corner radius on the ``INPUT`` host rather than a
    child ``CONTAINER``. Falls back to the host when it carries field chrome.
    """
    nested = _nested_input_area_host(node)
    if nested is not None:
        surface = primary_surface_node(nested)
        if surface is not None:
            return surface
        if nested.style.background_color is not None or nested.style.border_radius is not None:
            return nested
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
    """Return a single prefilled value ``TEXT`` inside a flex ``INPUT``, if unambiguous.

    When multiple non-chrome text leaves exist (nested form controls), returns ``None``
    so the host decomposes into child widgets instead of one collapsed field.

    Only excludes the hint node when it is an absolutely-positioned placeholder label
    (``stack_placement`` set), matching the heuristic absolute input-stack pattern.
    """
    chrome_ids = {id(item) for item in input_trailing_chrome_nodes(node)}
    hint = input_hint_node(node)
    hint_id = id(hint) if hint is not None and hint.stack_placement is not None else None
    parts: list[str] = []

    def walk(children: list[CleanDesignTreeNode], skip: bool) -> None:
        for child in children:
            child_skip = skip or id(child) in chrome_ids
            if (
                child.type == NodeType.TEXT
                and not child_skip
                and child.text
                and id(child) != hint_id
            ):
                parts.append(child.text.strip())
            if child.children:
                walk(child.children, child_skip)

    walk(node.children, False)
    if len(parts) != 1:
        return None
    return parts[0]


def input_trailing_chrome_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Return icon/vector subtrees that sit beside the value inside a flex ``INPUT``."""

    def collect(children: list[CleanDesignTreeNode]) -> None:
        for child in children:
            if child.type == NodeType.BUTTON and looks_like_input_trailing_icon_button(child) or child.type == NodeType.STACK and _stack_has_vector_icon(
                _descendant_nodes(child, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
            ) or child.type == NodeType.VECTOR and (
                child.vector_asset_key or child.style.has_stroke
            ):
                chrome.append(child)
            elif child.type in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER}:
                collect(child.children)

    chrome: list[CleanDesignTreeNode] = []
    collect(node.children)
    return chrome
