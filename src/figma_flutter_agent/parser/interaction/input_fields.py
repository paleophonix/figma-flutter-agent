"""Input and form field inspection utilities for Figma interactive nodes."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .icons import (
    _stack_has_vector_icon,
    layout_fact_input_trailing_icon_button,
)
from .shared import (
    _INPUT_TRAILING_ICON_DESCENDANT_DEPTH,
    _MAX_LOCAL_DEPTH,
    _descendant_nodes,
    _local_nodes,
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


_MIN_EXTERNAL_LABEL_GAP_PX = 4.0


def input_external_label_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return a ``TEXT`` label sibling above the painted input surface."""
    if node.type != NodeType.INPUT or not node.children:
        return None
    surface = input_surface_node(node)
    if surface is None:
        return None
    host_height = node.sizing.height
    if (host_height is None or host_height <= 0) and node.stack_placement is not None:
        host_height = node.stack_placement.height
    surface_height = surface.sizing.height
    if surface_height is None or surface_height <= 0:
        if surface.stack_placement is not None:
            surface_height = surface.stack_placement.height
    if host_height is None or surface_height is None:
        return None
    if float(host_height) <= float(surface_height) + _MIN_EXTERNAL_LABEL_GAP_PX:
        return None

    def label_in_chrome_group(item: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if item.type == NodeType.TEXT and (item.text or "").strip():
            return item
        if item.type in {NodeType.ROW, NodeType.COLUMN, NodeType.STACK}:
            for grand in item.children:
                if grand.type == NodeType.TEXT and (grand.text or "").strip():
                    return grand
        return None

    for child in node.children:
        if child.id == surface.id:
            continue
        if child.type == NodeType.INPUT and child.id == surface.id:
            continue
        found = label_in_chrome_group(child)
        if found is not None:
            return found
    return None


def input_hint_text(node: CleanDesignTreeNode) -> str:
    """Return placeholder label for an input-like stack group."""
    hint_node = input_hint_node(node)
    if hint_node is not None and hint_node.text:
        return hint_node.text.strip()
    if input_external_label_node(node) is not None:
        return ""
    return node.accessibility_label or node.name


def input_hint_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the placeholder ``TEXT`` node inside an input-like stack group."""
    external = input_external_label_node(node)
    for text_node in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if text_node.type == NodeType.TEXT and text_node.text:
            if external is not None and text_node.id == external.id:
                continue
            return text_node
    return None


def primary_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Pick the main painted surface inside a group (largest area)."""
    surfaces = [
        candidate
        for candidate in _local_nodes(node, _MAX_LOCAL_DEPTH)
        if candidate.type in {NodeType.CONTAINER, NodeType.INPUT, NodeType.VECTOR}
        and candidate.sizing.width
        and candidate.sizing.height
        and (candidate.style.background_color or candidate.style.border_color)
        and surface_covers_node(node, candidate)
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


def textarea_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Resolve painted field chrome inside a multiline textarea shell."""
    candidates: list[CleanDesignTreeNode] = []

    def walk(item: CleanDesignTreeNode) -> None:
        if item.type in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER, NodeType.INPUT}:
            has_border = bool(item.style.border_width and item.style.border_width > 0)
            has_fill = item.style.background_color is not None
            name_token = (item.name or "").strip().lower()
            if has_border or (has_fill and "field" in name_token):
                candidates.append(item)
        for child in item.children:
            walk(child)

    walk(node)
    if candidates:
        return max(
            candidates,
            key=lambda item: float(item.sizing.width or 0) * float(item.sizing.height or 0),
        )
    return primary_surface_node(node)


def input_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Resolve painted surface for flex/stack ``INPUT`` frames.

    Figma often applies fill and corner radius on the ``INPUT`` host rather than a
    child ``CONTAINER``. Falls back to the host when it carries field chrome.
    """
    surface = primary_surface_node(node)
    if surface is not None:
        return surface
    from .inline_input_hosts import layout_fact_flex_painted_input_surface

    for candidate in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if layout_fact_flex_painted_input_surface(candidate):
            return candidate
    if node.type == NodeType.INPUT and (
        node.style.background_color is not None or node.style.border_radius is not None
    ):
        return node
    return None


def input_value_style_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the prefilled value ``TEXT`` node inside a flex ``INPUT`` host."""
    chrome_ids = {id(item) for item in input_trailing_chrome_nodes(node)}
    hint = input_hint_node(node)
    external = input_external_label_node(node)
    hint_id = id(hint) if hint is not None else None
    external_id = external.id if external is not None else None
    candidates: list[CleanDesignTreeNode] = []

    def walk(children: list[CleanDesignTreeNode], skip: bool) -> None:
        for child in children:
            child_skip = skip or id(child) in chrome_ids
            if (
                child.type == NodeType.TEXT
                and not child_skip
                and child.text
                and id(child) != hint_id
                and child.id != external_id
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
    external = input_external_label_node(node)
    hint_id = id(hint) if hint is not None and hint.stack_placement is not None else None
    external_id = external.id if external is not None else None
    parts: list[str] = []

    def walk(children: list[CleanDesignTreeNode], skip: bool) -> None:
        for child in children:
            child_skip = skip or id(child) in chrome_ids
            if (
                child.type == NodeType.TEXT
                and not child_skip
                and child.text
                and id(child) != hint_id
                and child.id != external_id
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
            if (
                child.type == NodeType.BUTTON
                and layout_fact_input_trailing_icon_button(child)
                or child.type == NodeType.STACK
                and _stack_has_vector_icon(
                    _descendant_nodes(child, _INPUT_TRAILING_ICON_DESCENDANT_DEPTH)
                )
                or child.type == NodeType.VECTOR
                and (child.vector_asset_key or child.style.has_stroke)
            ):
                chrome.append(child)
            elif child.type in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER}:
                collect(child.children)

    chrome: list[CleanDesignTreeNode] = []
    collect(node.children)
    return chrome
