"""Figma component instance collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DedupResult:
    """Reusable widget candidates discovered in the design tree."""

    component_refs: dict[str, str] = field(default_factory=dict)
    instance_count: dict[str, int] = field(default_factory=dict)


def collect_component_instances(root: dict[str, Any]) -> DedupResult:
    """Collect component instance references from a Figma subtree."""
    result = DedupResult()

    def walk(node: dict[str, Any]) -> None:
        if node.get("visible") is False:
            return
        if node.get("type") == "INSTANCE":
            component_id = node.get("componentId")
            if component_id:
                result.component_refs[node["id"]] = component_id
                result.instance_count[component_id] = (
                    result.instance_count.get(
                        component_id,
                        0,
                    )
                    + 1
                )
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    return result
