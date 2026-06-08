"""Figma ValueKey helpers for AST sidecar chunking."""

from __future__ import annotations

import re

FIGMA_VALUE_KEY_RE = re.compile(r"ValueKey\('figma-([^']+)'\)")


def node_id_from_figma_key_suffix(suffix: str) -> str:
    """Invert ``figma_key_token`` (colon -> underscore) back to a Figma node id."""
    return suffix.replace("_", ":")


def discover_figma_node_ids(source: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for suffix in FIGMA_VALUE_KEY_RE.findall(source):
        node_id = node_id_from_figma_key_suffix(suffix)
        if node_id not in seen:
            seen.add(node_id)
            ordered.append(node_id)
    return ordered
