"""Validation gates for cluster widget extraction."""

from __future__ import annotations

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.widget_extractor import (
    cluster_has_top_level_usage,
    collect_cluster_widget_specs,
    count_cluster_nodes,
)
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode


def validate_annotated_widget_extraction(
    planned_files: dict[str, str],
    clean_trees: list[CleanDesignTreeNode],
    *,
    prefixes: list[str],
    widget_suffix: str,
    fail_on_unextracted: bool,
) -> None:
    """Fail when annotated layers did not produce widget files and layout refs."""
    if not fail_on_unextracted:
        return
    from figma_flutter_agent.generator.layout.common import to_snake_case
    from figma_flutter_agent.generator.widget_extraction.eligibility import (
        is_eligible_extraction_candidate,
    )
    from figma_flutter_agent.parser.annotations.widget_marker import (
        collect_annotated_widget_nodes,
    )

    layout_source = "\n".join(
        content for path, content in planned_files.items() if path.endswith("_layout.dart")
    )
    for tree in clean_trees:
        for node, class_name in collect_annotated_widget_nodes(
            tree,
            prefixes=prefixes,
            widget_suffix=widget_suffix,
        ):
            if not is_eligible_extraction_candidate(node):
                continue
            widget_path = f"lib/widgets/{to_snake_case(class_name)}.dart"
            if widget_path not in planned_files:
                raise GenerationError(
                    f"Annotated widget {class_name!r} for node {node.id} ({node.name!r}) "
                    f"requires {widget_path}"
                )
            if f"{class_name}(" not in layout_source:
                raise GenerationError(
                    f"Annotated widget {class_name!r} for node {node.id} ({node.name!r}) "
                    "is missing from layout references"
                )


def validate_inference_widget_extraction(
    planned_files: dict[str, str],
    specs: list[ClusterWidgetSpec],
) -> None:
    """Fail when semantic inference specs did not materialize widget files."""
    for spec in specs:
        if not spec.cluster_id.startswith("semantic_"):
            continue
        widget_path = f"lib/widgets/{spec.file_name}.dart"
        if widget_path not in planned_files:
            raise GenerationError(
                f"Inference widget {spec.class_name!r} requires generated file {widget_path}"
            )


def validate_cluster_widget_extraction(
    planned_files: dict[str, str],
    clean_trees: list[CleanDesignTreeNode],
    cluster_summary: dict[str, int],
    *,
    min_count: int,
    widget_suffix: str,
    enforce_cluster_widgets: bool,
    fail_duplicate_clusters: bool,
) -> None:
    """Fail when repeated structural clusters are not extracted into shared widgets."""
    if not fail_duplicate_clusters or not cluster_summary:
        return

    layout_source = "\n".join(
        content for path, content in planned_files.items() if path.endswith("_layout.dart")
    )
    specs_by_cluster: dict[str, ClusterWidgetSpec] = {}
    for tree in clean_trees:
        for spec in collect_cluster_widget_specs(
            tree,
            cluster_summary,
            min_count=min_count,
            widget_suffix=widget_suffix,
        ):
            specs_by_cluster.setdefault(spec.cluster_id, spec)

    for cluster_id, summary_count in sorted(cluster_summary.items()):
        if summary_count < min_count:
            continue
        node_count = count_cluster_nodes(clean_trees, cluster_id)
        if node_count < min_count:
            continue

        if cluster_id not in specs_by_cluster:
            raise GenerationError(
                f"Structural cluster '{cluster_id}' appears {summary_count} times "
                "but no representative node was found for widget extraction"
            )
        spec = specs_by_cluster[cluster_id]

        widget_path = f"lib/widgets/{spec.file_name}.dart"
        if widget_path not in planned_files:
            detail = (
                f"Structural cluster '{cluster_id}' requires widget '{widget_path}' "
                f"({node_count} occurrences)"
            )
            if enforce_cluster_widgets:
                detail += "; enforce_cluster_widgets is enabled but no widget was generated"
            raise GenerationError(detail)

        if cluster_has_top_level_usage(clean_trees, cluster_id):
            ref_token = f"{spec.class_name}("
            ref_count = layout_source.count(ref_token)
            if ref_count < node_count:
                raise GenerationError(
                    f"Structural cluster '{cluster_id}' has {node_count} occurrences but only "
                    f"{ref_count} reference(s) to '{spec.class_name}' in layout; "
                    "duplicate subtrees must use the extracted widget"
                )
