"""LLM prompt hints for reusable widget extraction."""

from __future__ import annotations

from figma_flutter_agent.parser.dedup.clusters import component_cluster_id
from figma_flutter_agent.parser.dedup.instances import DedupResult
from figma_flutter_agent.schemas import CleanDesignTreeNode


def build_widget_extraction_hints(
    dedup: DedupResult,
    cluster_summary: dict[str, int],
    *,
    clean_tree: CleanDesignTreeNode | None = None,
    annotation_prefixes: list[str] | None = None,
    widget_suffix: str = "Widget",
) -> list[str]:
    """Build LLM hints for reusable widget extraction."""
    hints: list[str] = []
    for component_id, count in sorted(dedup.instance_count.items()):
        if count >= 1:
            cluster = component_cluster_id(component_id)
            hints.append(
                f"Figma component '{component_id}' appears {count} time(s) "
                f"(cluster '{cluster}'); extract a reusable widget."
            )
    for cluster_id, count in sorted(cluster_summary.items()):
        hints.append(
            f"Structural cluster '{cluster_id}' appears {count} times; extract a shared widget."
        )
    if clean_tree is not None:
        from figma_flutter_agent.parser.annotations.widget_marker import (
            collect_annotated_widget_nodes,
        )

        for _node, class_name in collect_annotated_widget_nodes(
            clean_tree,
            prefixes=annotation_prefixes,
            widget_suffix=widget_suffix,
        ):
            hints.append(
                f"Layer annotation requires extracted widget {class_name!r}; "
                "emit kind=extracted with matching widgetIr."
            )
    return hints
