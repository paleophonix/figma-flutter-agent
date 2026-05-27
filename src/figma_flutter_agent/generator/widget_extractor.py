"""Deterministic reusable widget extraction from structural clusters."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.cluster_variants import collect_cluster_vector_variants
from figma_flutter_agent.generator.layout_renderer import render_node_body, render_widget_file
from figma_flutter_agent.generator.renderer import to_pascal_case, to_snake_case
from figma_flutter_agent.schemas import CleanDesignTreeNode


@dataclass(frozen=True)
class ClusterWidgetSpec:
    """Metadata for a cluster-backed reusable widget."""

    cluster_id: str
    class_name: str
    file_name: str
    representative: CleanDesignTreeNode


@dataclass(frozen=True)
class ClusterWidgetResult:
    """Generated cluster widget files and lookup tables."""

    files: dict[str, str]
    cluster_classes: dict[str, str]


def _cluster_label(node: CleanDesignTreeNode) -> str:
    """Prefer published component name for component-backed clusters."""
    if node.variant and node.variant.component_name:
        return str(node.variant.component_name).split("/")[0]
    return node.name


def _widget_class_name(node: CleanDesignTreeNode, cluster_id: str, widget_suffix: str) -> str:
    label = _cluster_label(node)
    base = to_pascal_case(label) or f"Cluster{cluster_id.split('_')[-1]}"
    if base.endswith(widget_suffix):
        return base
    return f"{base}{widget_suffix}"


def cluster_has_top_level_usage(trees: list[CleanDesignTreeNode], cluster_id: str) -> bool:
    """Return True when a cluster member is a direct child of a screen root node."""
    for tree in trees:
        for child in tree.children:
            if child.cluster_id == cluster_id:
                return True
    return False


def count_cluster_nodes(trees: list[CleanDesignTreeNode], cluster_id: str) -> int:
    """Count clean-tree nodes assigned to a structural cluster id."""
    total = 0

    def walk(node: CleanDesignTreeNode) -> None:
        nonlocal total
        if node.cluster_id == cluster_id:
            total += 1
        for child in node.children:
            walk(child)

    for tree in trees:
        walk(tree)
    return total


def collect_cluster_widget_specs(
    root: CleanDesignTreeNode,
    cluster_summary: dict[str, int],
    *,
    min_count: int = 2,
    widget_suffix: str = "Widget",
) -> list[ClusterWidgetSpec]:
    """Collect one representative node per repeated structural cluster.

    Args:
        root: Parsed clean design tree root.
        cluster_summary: Cluster id to occurrence count mapping.
        min_count: Minimum occurrences required to extract a widget.
        widget_suffix: Suffix appended to widget class names.

    Returns:
        Cluster widget specifications ordered by cluster id.
    """
    seen: set[str] = set()
    specs: list[ClusterWidgetSpec] = []

    def walk(node: CleanDesignTreeNode) -> None:
        cluster_id = node.cluster_id
        if (
            cluster_id
            and cluster_id not in seen
            and cluster_summary.get(cluster_id, 0) >= min_count
        ):
            seen.add(cluster_id)
            class_name = _widget_class_name(node, cluster_id, widget_suffix)
            specs.append(
                ClusterWidgetSpec(
                    cluster_id=cluster_id,
                    class_name=class_name,
                    file_name=to_snake_case(class_name),
                    representative=node,
                )
            )
        for child in node.children:
            walk(child)

    walk(root)
    return sorted(specs, key=lambda item: item.cluster_id)


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
    """Fail when repeated structural clusters are not extracted into shared widgets.

    Args:
        planned_files: Planned project files keyed by relative path.
        clean_trees: Parsed design trees (primary + destinations).
        cluster_summary: Structural cluster id to occurrence count mapping.
        min_count: Minimum cluster size required for extraction.
        widget_suffix: Widget class suffix from agent naming config.
        enforce_cluster_widgets: Whether cluster widget generation is enabled.
        fail_duplicate_clusters: When True, apply hard gates for duplicate clusters.

    Raises:
        GenerationError: When clusters are repeated but not represented by shared widgets.
    """
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


def render_cluster_widgets(
    specs: list[ClusterWidgetSpec],
    *,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    clean_trees: list[CleanDesignTreeNode] | None = None,
) -> ClusterWidgetResult:
    """Render deterministic widget files for structural clusters.

    Args:
        specs: Cluster widget specifications from ``collect_cluster_widget_specs``.
        uses_svg: Whether generated widgets may import ``flutter_svg``.
        package_name: Flutter package name for import URIs.
        use_package_imports: When True, emit package imports instead of relative paths.
        clean_trees: Optional parsed trees used to detect parameterized cluster variants.

    Returns:
        Widget file contents and cluster id to class name mapping.
    """
    files: dict[str, str] = {}
    cluster_classes = {spec.cluster_id: spec.class_name for spec in specs}
    vector_variants = (
        collect_cluster_vector_variants(
            clean_trees,
            {spec.cluster_id: spec.representative for spec in specs},
        )
        if clean_trees
        else {}
    )
    for spec in specs:
        variant = vector_variants.get(spec.cluster_id)
        body = render_node_body(
            spec.representative,
            uses_svg=uses_svg,
            cluster_classes=cluster_classes,
            skip_cluster_id=spec.cluster_id,
            cluster_vector_variant=variant,
        )
        widget_fields = ""
        constructor_params = "{super.key}"
        if variant is not None:
            widget_fields = f"  final bool {variant.param_name};\n\n"
            constructor_params = f"{{super.key, this.{variant.param_name} = true}}"
        path = f"lib/widgets/{spec.file_name}.dart"
        files[path] = render_widget_file(
            class_name=spec.class_name,
            body=body,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            source_file=path,
            widget_fields=widget_fields,
            constructor_params=constructor_params,
        )
    return ClusterWidgetResult(files=files, cluster_classes=cluster_classes)
