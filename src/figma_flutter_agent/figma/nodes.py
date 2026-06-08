"""Figma nodes API helpers."""

from __future__ import annotations

from typing import Any


def merge_figma_nodes_batch(
    target: dict[str, Any],
    batch_nodes: dict[str, Any] | None,
) -> list[str]:
    """Merge a Figma ``nodes`` map into *target*, skipping null entries."""
    if not isinstance(batch_nodes, dict):
        return []
    dropped: list[str] = []
    for node_id, entry in batch_nodes.items():
        if entry is None:
            dropped.append(node_id)
            continue
        target[node_id] = entry
    return dropped
