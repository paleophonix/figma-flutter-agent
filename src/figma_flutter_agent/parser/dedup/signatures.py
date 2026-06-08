"""Structural signatures for clean tree deduplication."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def node_signature_payload(
    node: CleanDesignTreeNode,
    *,
    include_text: bool,
) -> dict[str, Any]:
    """Build a JSON-serializable structural signature payload for a node."""
    payload: dict[str, Any] = {
        "type": node.type.value,
        "padding": node.padding.model_dump(),
        "spacing": node.spacing,
        "sizing": node.sizing.model_dump(by_alias=True),
        "alignment": node.alignment.model_dump(),
        "style": node.style.model_dump(by_alias=True),
        "children": [
            node_signature_payload(child, include_text=include_text)
            for child in node.children
        ],
    }
    if include_text:
        payload["text"] = node.text
    return payload


def structural_signature(node: CleanDesignTreeNode) -> str:
    """Return a stable hash for a clean-tree subtree including text content."""
    payload = json.dumps(
        node_signature_payload(node, include_text=True),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def descendant_text_fingerprint(node: CleanDesignTreeNode) -> tuple[str, ...]:
    """Collect visible TEXT copy so clusters do not merge headings with different labels."""
    texts: list[str] = []

    def walk(current: CleanDesignTreeNode) -> None:
        if current.type == NodeType.TEXT:
            raw = (current.text or current.name or "").strip()
            if raw:
                texts.append(raw)
        for child in current.children:
            walk(child)

    walk(node)
    return tuple(texts)


def cluster_structure_signature(node: CleanDesignTreeNode) -> str:
    """Return a stable hash for deduplication (layout/spacing + TEXT fingerprint)."""
    payload = node_signature_payload(node, include_text=False)
    text_fingerprint = descendant_text_fingerprint(node)
    if text_fingerprint:
        payload["textFingerprint"] = text_fingerprint
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
