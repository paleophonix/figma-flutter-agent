"""Cluster and subtree widget extraction helpers for the generation planner."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.cluster_variants import (
    collect_cluster_vector_variants,
    restore_pruned_cluster_vector_keys,
)
from figma_flutter_agent.generator.layout.common import to_snake_case
from figma_flutter_agent.generator.planned.reconcile import (
    repair_foreign_delegate_widget_builds,
    repair_stale_widget_ctor_names_in_planned,
)
from figma_flutter_agent.generator.subtree import (
    SubtreeWidgetResult,
    SubtreeWidgetSpec,
    plan_subtree_widget_files,
    replace_extracted_subtree_nodes_with_refs,
)
from figma_flutter_agent.generator.subtree.render import _subtree_render_root
from figma_flutter_agent.generator.widget_extractor import ClusterWidgetSpec
from figma_flutter_agent.parser.dedup.prune import (
    prune_decorative_absolute_vectors,
    prune_generation_layout_tree,
)
from figma_flutter_agent.generator.planner.context import GenerationPlanContext


def prune_decorative_vectors(context: GenerationPlanContext) -> None:
    """Prune decorative absolute Vector nodes from all generation trees.

    Args:
        context: Parsed design data, settings, and optional LLM output.
    """
    removed_vectors = prune_decorative_absolute_vectors(context.clean_tree)
    if removed_vectors:
        logger.info(
            "Pruned {} decorative absolute Vector node(s) from screen layout tree",
            removed_vectors,
        )
    for destination_tree in context.destination_trees.values():
        prune_decorative_absolute_vectors(destination_tree)


def apply_true_subtree_pruning(
    context: GenerationPlanContext,
    subtree_specs: list[SubtreeWidgetSpec],
) -> None:
    """Replace extracted subtree nodes with refs and prune the layout tree.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        subtree_specs: Extracted subtree widget specifications.
    """
    if not (context.settings.agent.generation.true_subtree_pruning and subtree_specs):
        return
    replace_extracted_subtree_nodes_with_refs(
        context.clean_tree,
        subtree_specs,
    )
    prune_generation_layout_tree(
        context.clean_tree,
        extracted_subtree_node_ids=frozenset(),
    )
    for destination_tree in context.destination_trees.values():
        prune_generation_layout_tree(
            destination_tree,
            extracted_subtree_node_ids=frozenset(),
        )


def collect_and_restore_cluster_vector_variants(
    context: GenerationPlanContext,
    cluster_specs: list[ClusterWidgetSpec],
    subtree_specs: list[SubtreeWidgetSpec],
    cluster_result,
) -> dict | None:
    """Collect cluster vector variants and restore pruned keys across trees.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        cluster_specs: Cluster widget specifications.
        subtree_specs: Extracted subtree widget specifications.
        cluster_result: Result of cluster widget rendering, or ``None``.

    Returns:
        Mapping of cluster ids to vector variants, or ``None`` if there is no
        cluster result to derive variants from.
    """
    if not (cluster_result and cluster_specs):
        return None
    variant_trees = [context.clean_tree, *context.destination_trees.values()]
    if subtree_specs:
        variant_trees.extend(
            _subtree_render_root(spec.representative) for spec in subtree_specs
        )
    cluster_vector_variants = collect_cluster_vector_variants(
        variant_trees,
        {spec.cluster_id: spec.representative for spec in cluster_specs},
    )
    restore_pruned_cluster_vector_keys(context.clean_tree, cluster_vector_variants)
    for destination_tree in context.destination_trees.values():
        restore_pruned_cluster_vector_keys(destination_tree, cluster_vector_variants)
    return cluster_vector_variants


def plan_subtree_widgets(
    context: GenerationPlanContext,
    planned_files: dict[str, str],
    subtree_specs: list[SubtreeWidgetSpec],
    *,
    uses_svg: bool,
    package_name: str,
    use_package_imports: bool,
    cluster_classes: dict | None,
    cluster_vector_variants: dict | None,
) -> tuple[dict[str, str], SubtreeWidgetResult | None]:
    """Repair planned delegates and plan subtree widget files.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        planned_files: Mapping of relative project paths to file contents.
        subtree_specs: Extracted subtree widget specifications.
        uses_svg: Whether the design references SVG assets.
        package_name: Flutter package name.
        use_package_imports: Whether to emit `package:` imports.
        cluster_classes: Mapping of cluster ids to generated class names.
        cluster_vector_variants: Mapping of cluster ids to vector variants.

    Returns:
        Tuple of updated planned files and the subtree widgets result, or
        ``(planned_files, None)`` if there are no subtree specs.
    """
    if not subtree_specs:
        return planned_files, None
    planned_files = repair_foreign_delegate_widget_builds(planned_files)
    planned_files = repair_stale_widget_ctor_names_in_planned(planned_files)
    planned_files, subtree_result = plan_subtree_widget_files(
        planned_files,
        subtree_specs,
        project_dir=context.project_dir,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        clean_tree=context.clean_tree,
    )
    return planned_files, subtree_result


def build_deterministic_widget_imports(
    cluster_specs: list[ClusterWidgetSpec],
    subtree_result: SubtreeWidgetResult | None,
) -> list[str]:
    """Build the sorted list of deterministic widget import stems.

    Args:
        cluster_specs: Cluster widget specifications.
        subtree_result: Result of subtree widget planning, or ``None``.

    Returns:
        Sorted, de-duplicated list of widget file stems to import.
    """
    deterministic_widget_imports = (
        [spec.file_name for spec in cluster_specs] if cluster_specs else []
    )
    if subtree_result is not None:
        deterministic_widget_imports.extend(
            to_snake_case(spec.class_name) for spec in subtree_result.specs
        )
    return sorted(set(deterministic_widget_imports))
