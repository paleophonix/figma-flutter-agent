"""Deterministic reusable widget extraction from structural clusters."""

from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from figma_flutter_agent.generator.cluster_variants import collect_cluster_vector_variants
from figma_flutter_agent.generator.layout import render_node_body, render_widget_file
from figma_flutter_agent.generator.layout.common import to_pascal_case, to_snake_case
from figma_flutter_agent.generator.widget_models import ClusterWidgetResult, ClusterWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _bound_cluster_widget_root(node: CleanDesignTreeNode, body: str) -> str:
    """Wrap extracted cluster roots so standalone widgets get finite ``Stack`` bounds."""
    from figma_flutter_agent.generator.layout.flex_policy import (
        _bound_stack_sized_box,
    )
    from figma_flutter_agent.generator.layout.widgets import _node_layout_size
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    if node.type == NodeType.STACK:
        bounded = _bound_stack_sized_box(node, body)
        if bounded is not None:
            return bounded
    width, height = _node_layout_size(node, node.stack_placement)
    if width is not None and height is not None and width > 0 and height > 0:
        return (
            f"SizedBox(width: {format_geometry_literal(width)}, "
            f"height: {format_geometry_literal(height)}, child: {body})"
        )
    if height is not None and height > 0:
        return f"SizedBox(height: {format_geometry_literal(height)}, child: {body})"
    return body


def _cluster_label(node: CleanDesignTreeNode) -> str:
    """Prefer published component name for component-backed clusters."""
    if node.variant and node.variant.component_name:
        return str(node.variant.component_name).split("/")[0]
    return node.name


_GENERIC_CLUSTER_LABELS = frozenset(
    {
        "button",
        "btn",
        "svg",
        "container",
        "frame",
        "group",
        "vector",
        "background",
        "overlay",
    }
)


def _widget_class_name(node: CleanDesignTreeNode, cluster_id: str, widget_suffix: str) -> str:
    label = _cluster_label(node)
    normalized = (to_pascal_case(label) or "").lower()
    stem = normalized.removesuffix("widget")
    if not stem or stem in _GENERIC_CLUSTER_LABELS:
        base = f"Cluster{cluster_id.split('_')[-1]}"
    else:
        base = to_pascal_case(label)
    if base.endswith(widget_suffix):
        return base
    return f"{base}{widget_suffix}"


def _representative_score(node: CleanDesignTreeNode) -> int:
    """Prefer default/enabled component variants when picking a cluster representative."""
    variant = node.variant
    if variant is None:
        return 25
    labels = [
        variant.component_name or "",
        variant.state or "",
        *variant.variant_properties.values(),
    ]
    lowered = " ".join(labels).lower()
    if "default" in lowered or "normal" in lowered or "enabled" in lowered:
        return 100
    if "disabled" in lowered:
        return 0
    return 50


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
    candidates: dict[str, list[CleanDesignTreeNode]] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        cluster_id = node.cluster_id
        if cluster_id and cluster_summary.get(cluster_id, 0) >= min_count:
            from figma_flutter_agent.parser.interaction import (
                layout_fact_hosts_compact_checkbox_control,
                layout_fact_hosts_payment_selection_indicator,
                must_inline_extracted_widget_host,
            )

            if must_inline_extracted_widget_host(node):
                for child in node.children:
                    walk(child)
                return
            if not layout_fact_hosts_compact_checkbox_control(node) and not layout_fact_hosts_payment_selection_indicator(
                node
            ):
                candidates.setdefault(cluster_id, []).append(node)
        for child in node.children:
            walk(child)

    walk(root)

    specs: list[ClusterWidgetSpec] = []
    from figma_flutter_agent.generator.variant_topology import compare_variant_topology

    def _topology_groups(nodes: list[CleanDesignTreeNode]) -> list[list[CleanDesignTreeNode]]:
        groups: list[list[CleanDesignTreeNode]] = []
        for node in nodes:
            matched = False
            for group in groups:
                if not compare_variant_topology(group[0], node).should_split:
                    group.append(node)
                    matched = True
                    break
            if not matched:
                groups.append([node])
        return groups

    for cluster_id, nodes in candidates.items():
        non_empty_nodes = [node for node in nodes if node.children]
        if non_empty_nodes:
            nodes = non_empty_nodes
        groups = _topology_groups(nodes)
        for group_index, group in enumerate(groups):
            representative = max(group, key=_representative_score)
            class_name = _widget_class_name(representative, cluster_id, widget_suffix)
            if len(groups) > 1:
                class_name = f"{class_name}Variant{group_index + 1}"
            specs.append(
                ClusterWidgetSpec(
                    cluster_id=cluster_id,
                    class_name=class_name,
                    file_name=to_snake_case(class_name),
                    representative=representative,
                )
            )
    existing_ids = {spec.cluster_id for spec in specs}
    specs.extend(
        _collect_component_family_widget_specs(
            root,
            min_count=min_count,
            widget_suffix=widget_suffix,
            existing_cluster_ids=existing_ids,
        )
    )
    return sorted(specs, key=lambda item: item.cluster_id)


def _component_id_for_node(node: CleanDesignTreeNode) -> str | None:
    from figma_flutter_agent.generator.cluster_variants import component_id_for_node

    return component_id_for_node(node)


def _collect_component_family_widget_specs(
    root: CleanDesignTreeNode,
    *,
    min_count: int,
    widget_suffix: str,
    existing_cluster_ids: set[str],
) -> list[ClusterWidgetSpec]:
    """Collect one widget per repeated published component family."""
    from collections import defaultdict

    from figma_flutter_agent.parser.dedup.clusters import component_cluster_id

    families: dict[str, list[CleanDesignTreeNode]] = defaultdict(list)

    def walk(node: CleanDesignTreeNode) -> None:
        component_id = _component_id_for_node(node)
        if component_id:
            families[component_id].append(node)
        for child in node.children:
            walk(child)

    walk(root)
    specs: list[ClusterWidgetSpec] = []
    for component_id, nodes in families.items():
        if len(nodes) < min_count:
            continue
        base_cluster_id = component_cluster_id(component_id)
        if base_cluster_id in existing_cluster_ids:
            continue
        from figma_flutter_agent.parser.interaction import (
            layout_fact_hosts_compact_checkbox_control,
            layout_fact_hosts_payment_selection_indicator,
            must_inline_extracted_widget_host,
        )

        eligible = [
            node
            for node in nodes
            if not must_inline_extracted_widget_host(node)
            and not layout_fact_hosts_compact_checkbox_control(node)
            and not layout_fact_hosts_payment_selection_indicator(node)
        ]
        if len(eligible) < min_count:
            continue
        with_children = [node for node in eligible if node.children]
        candidates = with_children if with_children else eligible
        representative = max(candidates, key=_representative_score)
        class_name = _widget_class_name(representative, base_cluster_id, widget_suffix)
        specs.append(
            ClusterWidgetSpec(
                cluster_id=base_cluster_id,
                class_name=class_name,
                file_name=to_snake_case(class_name),
                representative=representative,
            )
        )
        existing_cluster_ids.add(base_cluster_id)
    return specs


def _bound_cluster_widget_root_hug_width(node: CleanDesignTreeNode, body: str) -> str:
    """Wrap chip cluster roots with height only so labels can expand horizontally."""
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    height = node.sizing.height
    if height is not None and height > 0:
        return f"SizedBox(height: {format_geometry_literal(height)}, child: {body})"
    return body


def _try_render_compact_icon_cluster_body(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
) -> str | None:
    """Emit ``SvgPicture`` for compact single-vector cluster representatives."""
    from figma_flutter_agent.assets.composite_icons import (
        layout_fact_compact_vector_icon_export_node,
    )
    from figma_flutter_agent.generator.layout.common import escape_dart_string
    from figma_flutter_agent.generator.layout.widgets.svg import _render_svg_picture

    if not uses_svg or not layout_fact_compact_vector_icon_export_node(node):
        return None
    asset = node.vector_asset_key
    if asset is None:
        return None
    return _render_svg_picture(node, escape_dart_string(asset))


def _resolve_cluster_representative_assets(
    node: CleanDesignTreeNode,
    project_dir: Path,
) -> CleanDesignTreeNode:
    """Return a copy of ``node`` with on-disk vector assets attached when discoverable."""
    from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
    from figma_flutter_agent.parser.boundaries.assets import (
        resolve_discovered_vector_asset_keys,
        resolve_pruned_cluster_instance_assets,
    )

    resolved = deep_copy_clean_tree(node)
    resolve_discovered_vector_asset_keys(resolved, project_dir)
    resolve_pruned_cluster_instance_assets(resolved, project_dir)
    return resolved


def render_cluster_widgets(
    specs: list[ClusterWidgetSpec],
    *,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    clean_trees: list[CleanDesignTreeNode] | None = None,
    project_dir: Path | None = None,
) -> ClusterWidgetResult:
    """Render deterministic widget files for structural clusters.

    Args:
        specs: Cluster widget specifications from ``collect_cluster_widget_specs``.
        uses_svg: Whether generated widgets may import ``flutter_svg``.
        package_name: Flutter package name for import URIs.
        use_package_imports: When True, emit package imports instead of relative paths.
        clean_trees: Optional parsed trees used to detect parameterized cluster variants.
        project_dir: When set, discover on-disk SVG exports before emit.

    Returns:
        Widget file contents and cluster id to class name mapping.
    """
    files: dict[str, str] = {}
    cluster_classes = {spec.cluster_id: spec.class_name for spec in specs}
    from figma_flutter_agent.generator.cluster_variants import component_id_for_node
    from figma_flutter_agent.parser.dedup.clusters import component_cluster_id

    for spec in specs:
        component_id = component_id_for_node(spec.representative)
        if component_id:
            cluster_classes.setdefault(
                component_cluster_id(component_id),
                spec.class_name,
            )
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
        from figma_flutter_agent.generator.cluster_variants import (
            chip_label_widget_defaults,
            cluster_uses_chip_variant_labels,
            parameterize_chip_hug_width_widget_body,
            parameterize_chip_label_widget_body,
        )

        chip_cluster = clean_trees is not None and cluster_uses_chip_variant_labels(
            clean_trees, spec.cluster_id
        )
        representative = spec.representative
        if project_dir is not None:
            representative = _resolve_cluster_representative_assets(
                representative,
                project_dir,
            )
        compact_body = _try_render_compact_icon_cluster_body(
            representative,
            uses_svg=uses_svg,
        )
        if compact_body is not None:
            body = compact_body
        elif chip_cluster:
            from figma_flutter_agent.generator.layout.widgets.option_chip import (
                render_tag_option_chip_body,
                wrap_tag_option_chip_interactive,
            )

            body = render_tag_option_chip_body(representative, clean_trees=clean_trees)
            body = wrap_tag_option_chip_interactive(
                body,
                representative,
                theme_variant="material_3",
            )
        else:
            body = render_node_body(
                representative,
                uses_svg=uses_svg,
                cluster_classes=cluster_classes,
                skip_cluster_id=spec.cluster_id,
                cluster_vector_variant=variant,
            )
        if chip_cluster:
            body = _bound_cluster_widget_root_hug_width(spec.representative, body)
        else:
            body = _bound_cluster_widget_root(spec.representative, body)
        widget_fields = ""
        constructor_params = "{super.key}"
        if chip_cluster:
            default_label, _default_selected = chip_label_widget_defaults(representative)
            body = parameterize_chip_label_widget_body(body, default_label)
            body = parameterize_chip_hug_width_widget_body(body)
            widget_fields = "  final String label;\n  final bool isSelected;\n\n"
            constructor_params = (
                f"{{super.key, this.label = '{default_label}', this.isSelected = false}}"
            )
        elif variant is not None:
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


def _find_cluster_representative(
    root: CleanDesignTreeNode,
    cluster_id: str,
) -> CleanDesignTreeNode | None:
    """Return the first clean-tree node tagged with ``cluster_id``."""
    found: CleanDesignTreeNode | None = None

    def walk(node: CleanDesignTreeNode) -> None:
        nonlocal found
        if found is not None:
            return
        if node.cluster_id == cluster_id:
            found = node
            return
        for child in node.children:
            walk(child)

    walk(root)
    return found


def materialize_missing_cluster_delegate_files(
    planned_files: dict[str, str],
    *,
    clean_tree: CleanDesignTreeNode,
    cluster_classes: dict[str, str],
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    project_dir: Path | None = None,
) -> dict[str, str]:
    """Emit cluster widget files referenced by planned sources but missing on disk."""
    import re

    from figma_flutter_agent.generator.planned.reconcile.class_inspect import (
        preferred_widget_path_for_class,
    )

    referenced_classes = {
        match
        for source in planned_files.values()
        for match in re.findall(r"\b(Cluster\w+Widget)\b", source)
    }
    if not referenced_classes:
        return planned_files
    class_to_cluster = {class_name: cluster_id for cluster_id, class_name in cluster_classes.items()}
    missing_specs: list[ClusterWidgetSpec] = []
    for class_name in sorted(referenced_classes):
        cluster_id = class_to_cluster.get(class_name)
        if cluster_id is None:
            continue
        preferred = preferred_widget_path_for_class(class_name)
        legacy = f"lib/widgets/{to_snake_case(class_name)}.dart"
        if preferred in planned_files or legacy in planned_files:
            continue
        representative = _find_cluster_representative(clean_tree, cluster_id)
        if representative is None:
            continue
        missing_specs.append(
            ClusterWidgetSpec(
                cluster_id=cluster_id,
                class_name=class_name,
                file_name=to_snake_case(class_name),
                representative=representative,
            )
        )
    if not missing_specs:
        return planned_files
    result = render_cluster_widgets(
        missing_specs,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        clean_trees=[clean_tree],
        project_dir=project_dir,
    )
    merged = dict(planned_files)
    merged.update(result.files)
    return merged


def refresh_cluster_widget_planned_files(
    planned: dict[str, str],
    *,
    clean_tree: CleanDesignTreeNode,
    cluster_summary: dict[str, int],
    min_count: int = 2,
    widget_suffix: str = "Widget",
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    destination_trees: dict[str, CleanDesignTreeNode] | None = None,
    project_dir: Path | None = None,
) -> dict[str, str]:
    """Re-render cluster widgets whose planned bodies are stubs or foreign delegates."""
    from figma_flutter_agent.generator.planned.reconcile import (
        _is_foreign_delegate_widget_build,
        _is_self_referential_widget_build,
        _is_shrink_only_widget_source,
        preferred_widget_path_for_class,
    )

    specs = collect_cluster_widget_specs(
        clean_tree,
        cluster_summary,
        min_count=min_count,
        widget_suffix=widget_suffix,
    )
    if not specs:
        return planned

    to_render: list[ClusterWidgetSpec] = []
    for spec in specs:
        preferred = preferred_widget_path_for_class(spec.class_name)
        existing = (planned.get(preferred) or "").strip()
        if not existing:
            continue
        if (
            _is_shrink_only_widget_source(existing)
            or _is_self_referential_widget_build(existing, spec.class_name)
            or _is_foreign_delegate_widget_build(existing, spec.class_name)
        ):
            to_render.append(spec)

    if not to_render:
        return planned

    clean_trees = [clean_tree]
    if destination_trees:
        clean_trees.extend(destination_trees.values())
    started = time.monotonic()
    result = render_cluster_widgets(
        to_render,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        clean_trees=clean_trees,
        project_dir=project_dir,
    )
    logger.info(
        "Refreshed {} cluster widget(s) in {:.1f}s",
        len(to_render),
        time.monotonic() - started,
    )
    merged = dict(planned)
    for spec in to_render:
        legacy_path = f"lib/widgets/{spec.file_name}.dart"
        preferred = preferred_widget_path_for_class(spec.class_name)
        fresh = result.files.get(preferred) or result.files.get(legacy_path)
        if fresh is None:
            continue
        merged[preferred] = fresh
        if legacy_path != preferred:
            merged.pop(legacy_path, None)
    return merged
