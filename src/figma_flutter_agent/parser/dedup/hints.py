"""LLM prompt hints for reusable widget extraction."""

from __future__ import annotations

from figma_flutter_agent.parser.dedup.clusters import component_cluster_id
from figma_flutter_agent.parser.dedup.instances import DedupResult


def build_widget_extraction_hints(
    dedup: DedupResult,
    cluster_summary: dict[str, int],
) -> list[str]:
    """Build LLM hints for reusable widget extraction."""
    hints: list[str] = []
    for component_id, count in sorted(dedup.instance_count.items()):
        if count >= 2:
            cluster = component_cluster_id(component_id)
            hints.append(
                f"Figma component '{component_id}' appears {count} times "
                f"(cluster '{cluster}'); extract a reusable widget."
            )
    for cluster_id, count in sorted(cluster_summary.items()):
        hints.append(
            f"Structural cluster '{cluster_id}' appears {count} times; extract a shared widget."
        )
    return hints
