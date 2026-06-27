"""Component metadata extraction from Figma payloads."""

from __future__ import annotations

import re
from typing import Any

from figma_flutter_agent.parser.component_raw import (
    is_leaf_graphic_node,
    is_raw_graphic_type,
    node_bbox_size,
    raw_looks_like_bottom_cta_footer,
)
from figma_flutter_agent.schemas import ComponentVariant, NodeType

_SEMANTIC_NAME_HINTS: tuple[tuple[tuple[str, ...], NodeType], ...] = (
    (("checkbox", "check box"), NodeType.CHECKBOX),
    (("switch", "toggle"), NodeType.SWITCH),
    (("radio group", "radiogroup"), NodeType.RADIO_GROUP),
    (("radio", "radio button"), NodeType.RADIO),
    (("dropdown", "drop down", "select", "combobox"), NodeType.DROPDOWN),
    (("dialog", "modal", "alert", "popup"), NodeType.DIALOG),
    (("slider", "range"), NodeType.SLIDER),
    (("carousel", "pager", "swiper", "slideshow"), NodeType.CAROUSEL),
    (("bottom nav", "bottom navigation", "bottom bar", "tab bar"), NodeType.BOTTOM_NAV),
    (("tab group", "tab view", "tab panel"), NodeType.TABS),
    (("tabs",), NodeType.TABS),
    (("button", "btn"), NodeType.BUTTON),
    (("input", "textfield", "text field"), NodeType.INPUT),
    (("card",), NodeType.CARD),
)

_NAME_FALLBACK_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CARD,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
        NodeType.CAROUSEL,
    }
)

_VARIANT_PROPERTY_KEYS = frozenset({"type", "role", "variant", "component", "control"})
_MAX_COMPACT_CARD_GLYPH_SPAN = 36.0
_MAX_SLIDER_HOST_HEIGHT_PX = 56.0
_MIN_HORIZONTAL_CARD_PEER_WIDTH_PX = 100.0
_MIN_HORIZONTAL_CARD_PEER_HEIGHT_PX = 48.0


def _raw_is_compact_vector_glyph_host(node: dict[str, Any]) -> bool:
    """Return True when a raw node is a compact icon glyph host, not a layout card."""
    bbox = node_bbox_size(node)
    if bbox is None:
        return False
    width, height = bbox
    if width <= 0 or height <= 0:
        return False
    if width > _MAX_COMPACT_CARD_GLYPH_SPAN or height > _MAX_COMPACT_CARD_GLYPH_SPAN:
        return False

    def walk(raw: dict[str, Any]) -> bool:
        raw_type = str(raw.get("type") or "")
        if raw_type == "TEXT":
            return not str(raw.get("characters") or "").strip()
        if is_raw_graphic_type(raw_type):
            return True
        children = raw.get("children") or []
        if not children:
            return raw_type in {"FRAME", "GROUP", "INSTANCE", "COMPONENT", "RECTANGLE"}
        return all(walk(child) for child in children)

    if not walk(node):
        return False

    def has_graphic_descendant(raw: dict[str, Any]) -> bool:
        if is_raw_graphic_type(str(raw.get("type") or "")):
            return True
        return any(has_graphic_descendant(child) for child in (raw.get("children") or []))

    return has_graphic_descendant(node)


def _raw_is_horizontal_card_peer(node: dict[str, Any]) -> bool:
    """Return True when a raw child looks like a carousel card tile, not a slider thumb."""
    bbox = node_bbox_size(node)
    if bbox is not None:
        width, height = bbox
        if (
            width >= _MIN_HORIZONTAL_CARD_PEER_WIDTH_PX
            and height >= _MIN_HORIZONTAL_CARD_PEER_HEIGHT_PX
        ):
            return True
    name = str(node.get("name") or "").lower()
    return "card" in name and str(node.get("type") or "") == "INSTANCE"


def _raw_hosts_horizontal_scroll_card_peers(node: dict[str, Any]) -> bool:
    """Return True when a raw subtree hosts a horizontal scroll row of card-like peers."""

    def horizontal_card_peer_count(raw: dict[str, Any]) -> int:
        layout_mode = str(raw.get("layoutMode") or "").upper()
        overflow = str(raw.get("overflowDirection") or "").upper()
        is_horizontal_row = layout_mode == "HORIZONTAL" or overflow == "HORIZONTAL"
        children = raw.get("children") or []
        if not is_horizontal_row or len(children) < 2:
            return 0
        return sum(1 for child in children if _raw_is_horizontal_card_peer(child))

    def walk(raw: dict[str, Any]) -> bool:
        if horizontal_card_peer_count(raw) >= 2:
            return True
        return any(walk(child) for child in (raw.get("children") or []))

    return walk(node)


def _raw_has_slider_track_anatomy(node: dict[str, Any]) -> bool:
    """Return True when raw geometry matches a compact slider track host."""
    bbox = node_bbox_size(node)
    if bbox is None:
        return False
    _, height = bbox
    return 0 < height <= _MAX_SLIDER_HOST_HEIGHT_PX


def match_semantic_type_from_name(name: str) -> NodeType | None:
    """Map a Figma layer or component name to a semantic clean-tree type."""
    lowered = name.lower().strip()
    camel_spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).lower().strip()
    for candidate in (lowered, camel_spaced):
        tokens = {token for token in re.split(r"[/\-_\s]+", candidate) if token}
        padded = f" {candidate} "
        for hints, node_type in _SEMANTIC_NAME_HINTS:
            if any(hint in tokens or hint == candidate or f" {hint} " in padded for hint in hints):
                return node_type
    return None


def validate_semantic_type_for_node(node: dict[str, Any], semantic: NodeType) -> bool:
    """Cross-validate name-inferred interactive types against geometry and structure.

    Args:
        node: Raw Figma node dictionary.
        semantic: Candidate semantic type from a name hint.

    Returns:
        True when the node may safely receive the semantic type.
    """
    if semantic not in _NAME_FALLBACK_INTERACTIVE_TYPES:
        return True
    if is_leaf_graphic_node(node):
        return False
    raw_type = str(node.get("type") or "")
    if semantic in {NodeType.BUTTON, NodeType.INPUT} and is_leaf_graphic_node(node):
        return False
    bbox = node_bbox_size(node)
    if bbox is not None and (bbox[0] <= 0 or bbox[1] <= 0):
        return False
    if semantic == NodeType.CARD:
        children = node.get("children") or []
        if is_raw_graphic_type(raw_type) and not children:
            return False
        if _raw_is_compact_vector_glyph_host(node):
            return False
    if semantic == NodeType.BOTTOM_NAV:
        if raw_looks_like_bottom_cta_footer(node):
            return False
        name = str(node.get("name") or "").lower()
        if "display down" in name or "home indicator" in name:
            return False
    if semantic == NodeType.SLIDER:
        if _raw_hosts_horizontal_scroll_card_peers(node):
            return False
        if not _raw_has_slider_track_anatomy(node):
            return False
    return True


def match_semantic_type_from_name_fallback(
    node: dict[str, Any],
    name: str,
) -> NodeType | None:
    """Name-hint semantic match used only when Components/Variables API has no signal."""
    candidate = match_semantic_type_from_name(name)
    if candidate is None:
        return None
    if not validate_semantic_type_for_node(node, candidate):
        return None
    return candidate


def _match_semantic_from_metadata(
    node: dict[str, Any],
    *candidates: object,
) -> NodeType | None:
    """Match semantic type from published component or set metadata fields."""
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            matched = match_semantic_type_from_name_fallback(node, candidate)
            if matched is not None:
                return matched
    return None


def infer_semantic_type_from_component_properties(node: dict[str, Any]) -> NodeType | None:
    """Infer semantic type from Figma instance ``componentProperties`` (variant axes).

    Args:
        node: Raw Figma node dictionary.

    Returns:
        Semantic node type when a variant property value matches a known pattern.
    """
    if node.get("type") != "INSTANCE":
        return None

    for prop_name, prop_value in (node.get("componentProperties") or {}).items():
        if not isinstance(prop_value, dict):
            continue
        key = str(prop_name).lower().strip()
        if key not in _VARIANT_PROPERTY_KEYS:
            continue
        raw_value = prop_value.get("value")
        if raw_value is None:
            continue
        matched = match_semantic_type_from_name_fallback(node, str(raw_value))
        if matched is not None:
            return matched
    return None


def infer_semantic_type_from_figma_overlay(node: dict[str, Any]) -> NodeType | None:
    """Infer dialog type from Figma prototype overlay fields (not layer naming).

    Args:
        node: Raw Figma node dictionary.

    Returns:
        ``DIALOG`` when the node carries Figma overlay presentation metadata.
    """
    if node.get("type") not in {"FRAME", "COMPONENT", "INSTANCE"}:
        return None
    if node.get("overlayPositionType") is not None:
        return NodeType.DIALOG
    if node.get("overlayBackground") is not None:
        return NodeType.DIALOG
    return None


def infer_semantic_type_from_component(
    node: dict[str, Any],
    components: dict[str, dict[str, Any]] | None,
    component_sets: dict[str, dict[str, Any]] | None = None,
) -> NodeType | None:
    """Infer semantic node type from a published component definition.

    Uses component set name, published component name/description, and set description.
    Does **not** use the instance layer name (that is a separate fallback in
    ``resolve_semantic_node_type`` only when Components API data is absent).

    Args:
        node: Raw Figma node dictionary.
        components: Published components map from the Components API.
        component_sets: Published component sets map from the Components API.

    Returns:
        Semantic node type when the instance maps to a known component pattern.
    """
    if node.get("type") != "INSTANCE":
        return None

    component_id = node.get("componentId")
    if not component_id:
        return None

    component_meta = (components or {}).get(component_id, {})
    component_set_id = component_meta.get("componentSetId")
    if isinstance(component_set_id, str) and component_sets:
        set_meta = component_sets.get(component_set_id, {})
        matched = _match_semantic_from_metadata(
            node,
            set_meta.get("name"),
            set_meta.get("description"),
        )
        if matched is not None:
            return matched

    return _match_semantic_from_metadata(
        node,
        component_meta.get("name"),
        component_meta.get("description"),
    )


def resolve_semantic_node_type(
    node: dict[str, Any],
    components: dict[str, dict[str, Any]] | None,
    component_sets: dict[str, dict[str, Any]] | None = None,
) -> NodeType | None:
    """Resolve semantic node type using Components API metadata, then safe fallbacks.

    For ``INSTANCE`` nodes with a ``componentId`` and a non-empty ``components`` map,
    layer names are **not** used when API metadata does not match — avoids mis-labeling
    generic instance names such as ``State=Default``.

    Args:
        node: Raw Figma node dictionary.
        components: Published components map from the Components API.
        component_sets: Published component sets map from the Components API.

    Returns:
        Semantic node type when recognized, otherwise ``None``.
    """
    if node.get("type") == "INSTANCE":
        component_type = infer_semantic_type_from_component(node, components, component_sets)
        if component_type is None:
            component_type = infer_semantic_type_from_component_properties(node)
        if component_type is not None:
            return component_type
        if node.get("componentId") and components:
            return None

    overlay_type = infer_semantic_type_from_figma_overlay(node)
    if overlay_type is not None:
        return overlay_type

    node_name = node.get("name")
    if isinstance(node_name, str) and node_name.strip():
        return match_semantic_type_from_name_fallback(node, node_name)
    return None


def extract_component_variant(
    node: dict[str, Any],
    components: dict[str, dict[str, Any]] | None,
) -> ComponentVariant | None:
    """Extract component variant metadata for a Figma instance node.

    Args:
        node: Raw Figma node dictionary.
        components: Published components map from the Components API.

    Returns:
        Component variant metadata when the node is a component instance.
    """
    if node.get("type") != "INSTANCE":
        return None

    component_id = node.get("componentId")
    if not component_id:
        return None

    component_meta = (components or {}).get(component_id, {})
    variant_properties: dict[str, str] = {}
    for prop_name, prop_value in (node.get("componentProperties") or {}).items():
        if isinstance(prop_value, dict):
            raw_value = prop_value.get("value")
            if raw_value is not None:
                variant_properties[prop_name] = str(raw_value)

    state = variant_properties.get("State") or variant_properties.get("state")
    return ComponentVariant(
        component_id=component_id,
        component_set_id=component_meta.get("componentSetId"),
        component_name=component_meta.get("name") or node.get("name"),
        variant_properties=variant_properties,
        state=state,
    )
