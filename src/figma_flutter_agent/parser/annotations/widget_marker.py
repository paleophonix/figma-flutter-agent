"""Parse strict layer-name widget extraction markers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from figma_flutter_agent.generator.layout.common import sanitize_dart_type_name, to_pascal_case
from figma_flutter_agent.schemas import CleanDesignTreeNode

_DEFAULT_PREFIX = "@widget"
_MARKER_PATTERN = re.compile(
    r"^(?P<prefix>@widget)(?:[ :](?P<name>.+))?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WidgetAnnotation:
    """Parsed widget extraction marker from a Figma layer name."""

    prefix: str
    requested_name: str | None
    raw_layer_name: str


def parse_widget_annotation(
    layer_name: str,
    prefixes: list[str] | None = None,
) -> WidgetAnnotation | None:
    """Return a widget marker when ``layer_name`` matches a configured prefix."""
    normalized = (layer_name or "").strip()
    if not normalized:
        return None
    allowed = {_normalize_prefix(item) for item in (prefixes or [_DEFAULT_PREFIX])}
    match = _MARKER_PATTERN.match(normalized)
    if match is None:
        return None
    prefix = match.group("prefix").lower()
    if prefix not in allowed:
        return None
    requested = (match.group("name") or "").strip() or None
    return WidgetAnnotation(
        prefix=prefix,
        requested_name=requested,
        raw_layer_name=normalized,
    )


def resolve_widget_class_name(
    annotation: WidgetAnnotation,
    *,
    layer_name: str,
    widget_suffix: str,
) -> str:
    """Resolve a public widget class name from a marker and fallback layer label."""
    stem_source = annotation.requested_name or _strip_marker_prefix(
        annotation.raw_layer_name,
        annotation.prefix,
    )
    stem_source = stem_source or layer_name
    stem = _annotation_stem_to_pascal(stem_source)
    if stem.endswith(widget_suffix):
        return stem
    return f"{stem}{widget_suffix}"


def apply_widget_layer_annotations(
    root: CleanDesignTreeNode,
    *,
    prefixes: list[str] | None = None,
    widget_suffix: str = "Widget",
) -> None:
    """Set ``extracted_widget_ref`` on nodes whose layer names carry widget markers."""

    def walk(node: CleanDesignTreeNode) -> None:
        annotation = parse_widget_annotation(node.name, prefixes)
        if annotation is not None:
            class_name = resolve_widget_class_name(
                annotation,
                layer_name=node.name,
                widget_suffix=widget_suffix,
            )
            node.extracted_widget_ref = class_name
        for child in node.children:
            walk(child)

    walk(root)


def collect_annotated_widget_nodes(
    root: CleanDesignTreeNode,
    *,
    prefixes: list[str] | None = None,
    widget_suffix: str = "Widget",
) -> list[tuple[CleanDesignTreeNode, str]]:
    """Return annotated nodes and their resolved widget class names."""
    found: list[tuple[CleanDesignTreeNode, str]] = []

    def walk(node: CleanDesignTreeNode) -> None:
        annotation = parse_widget_annotation(node.name, prefixes)
        if annotation is not None:
            class_name = resolve_widget_class_name(
                annotation,
                layer_name=node.name,
                widget_suffix=widget_suffix,
            )
            found.append((node, class_name))
        for child in node.children:
            walk(child)

    walk(root)
    return found


def _normalize_prefix(prefix: str) -> str:
    return prefix.strip().lower()


def _strip_marker_prefix(layer_name: str, prefix: str) -> str:
    lowered = layer_name.strip()
    token = prefix.lower()
    if lowered.lower().startswith(token):
        remainder = lowered[len(token) :].lstrip(" :")
        return remainder.strip()
    return lowered


def _annotation_stem_to_pascal(value: str) -> str:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value.strip())
    spaced = re.sub(r"[_\-]+", " ", spaced)
    pascal = to_pascal_case(spaced)
    return sanitize_dart_type_name(pascal) or "Extracted"
