"""Emit conservation checks: pre-emit facts must survive layout + chunk materialization."""

from __future__ import annotations

import re
from collections.abc import Mapping

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_CHUNK_CLASS_REF_RE = re.compile(r"\b(FigmaChunk[A-F0-9]+)\b")
_MIN_CHUNK_BODY_CHARS = 120


def collect_mandatory_text_survivors(root: CleanDesignTreeNode) -> set[str]:
    """Return distinct TEXT payloads that must appear somewhere in planned Dart emit.

    Args:
        root: Clean design tree used for offline emit.

    Returns:
        Non-empty stripped text strings from TEXT nodes.
    """
    survivors: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.type == NodeType.TEXT:
            text = (node.text or node.accessibility_label or "").strip()
            if text:
                survivors.add(text)
        for child in node.children:
            walk(child)

    walk(root)
    return survivors


def _combined_dart_source(planned_dart: Mapping[str, str]) -> str:
    return "\n".join(content for path, content in planned_dart.items() if path.endswith(".dart"))


def find_missing_text_survivors(
    root: CleanDesignTreeNode,
    planned_dart: Mapping[str, str],
) -> list[str]:
    """List mandatory TEXT strings absent from all planned Dart files.

    Args:
        root: Clean design tree.
        planned_dart: Project-relative planned Dart paths to contents.

    Returns:
        Sorted missing text labels.
    """
    combined = _combined_dart_source(planned_dart)
    return sorted(
        label for label in collect_mandatory_text_survivors(root) if label not in combined
    )


def find_unmaterialized_chunk_refs(planned_dart: Mapping[str, str]) -> list[str]:
    """Return chunk class names referenced in layout but missing substantive bodies.

    A layout ``const FigmaChunk…()`` must have a matching generated chunk file whose
    build method is not an empty or import-only stub.

    Args:
        planned_dart: Project-relative planned Dart paths to contents.

    Returns:
        Sorted unmaterialized chunk class names.
    """
    layout_sources = [
        content
        for path, content in planned_dart.items()
        if path.replace("\\", "/").endswith("_layout.dart")
    ]
    if not layout_sources:
        return []

    refs = {match for source in layout_sources for match in _CHUNK_CLASS_REF_RE.findall(source)}
    if not refs:
        return []

    chunk_bodies = {
        class_name: body
        for path, body in planned_dart.items()
        if "_chunk_" in path.replace("\\", "/")
        for class_name in _CHUNK_CLASS_REF_RE.findall(body)
        if f"class {class_name}" in body
    }
    # Also map stem -> body for classes only referenced from layout imports.
    for path, body in planned_dart.items():
        if "_chunk_" not in path.replace("\\", "/"):
            continue
        for class_name in _CHUNK_CLASS_REF_RE.findall(body):
            if f"class {class_name}" in body:
                chunk_bodies.setdefault(class_name, body)

    missing: list[str] = []
    for class_name in sorted(refs):
        body = chunk_bodies.get(class_name, "")
        build_idx = body.find("Widget build(")
        build_tail = body[build_idx:] if build_idx >= 0 else body
        if len(build_tail.strip()) < _MIN_CHUNK_BODY_CHARS:
            missing.append(class_name)
    return missing
