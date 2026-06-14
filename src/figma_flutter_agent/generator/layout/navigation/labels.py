"""Label helpers for navigation widgets."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.schemas import CleanDesignTreeNode

_GARBAGE_NAV_NAME_TOKENS = (
    "rectangle",
    "icon /",
    "icon/",
    "icosn/",
    "ellipse",
    "group ",
    "vector",
    "container",
    "frame",
)
_ICON_LAYER_NAME_RE = re.compile(r"icon\s*/\s*\d+")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _sanitize_figma_layer_name(name: str) -> str:
    """Strip non-printable control characters from Figma layer names."""
    cleaned = _CONTROL_CHAR_RE.sub("", name)
    return cleaned.strip()


def _layer_name_is_garbage_nav_label(name: str) -> bool:
    lowered = _sanitize_figma_layer_name(name).lower()
    if not lowered:
        return True
    if _ICON_LAYER_NAME_RE.search(lowered):
        return True
    return any(token in lowered for token in _GARBAGE_NAV_NAME_TOKENS)


def first_descendant_text_label(
    node: CleanDesignTreeNode, *, max_depth: int = 8, depth: int = 0
) -> str | None:
    if depth > max_depth:
        return None
    if node.text and node.text.strip():
        return node.text.strip()
    for child in node.children:
        found = first_descendant_text_label(
            child,
            max_depth=max_depth,
            depth=depth + 1,
        )
        if found:
            return found
    return None


def label_from_child(child: CleanDesignTreeNode) -> str:
    """Resolve a tab or nav item label from a child node."""
    label = first_descendant_text_label(child)
    if label:
        return escape_dart_string(_sanitize_figma_layer_name(label))
    name = _sanitize_figma_layer_name(child.name)
    if _layer_name_is_garbage_nav_label(name):
        return ""
    return escape_dart_string(name)


def tab_label_from_child(child: CleanDesignTreeNode) -> str:
    """Use panel frame names for tab labels (not inner headline text)."""
    return escape_dart_string(child.name)
