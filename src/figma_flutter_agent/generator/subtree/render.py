"""Rendering subtree widgets."""

from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from figma_flutter_agent.generator.layout import render_node_body, render_widget_file
from figma_flutter_agent.generator.subtree.spec import (
    SubtreeWidgetResult,
    SubtreeWidgetSpec,
    collect_subtree_widget_specs,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def build_cluster_render_context(
    clean_tree: CleanDesignTreeNode,
    *,
    cluster_summary: dict[str, int],
    widget_suffix: str = "Widget",
    min_count: int = 2,
    destination_trees: dict[str, CleanDesignTreeNode] | None = None,
) -> tuple[dict[str, str] | None, dict | None]:
    """Build ``cluster_classes`` / ``cluster_vector_variants`` for subtree and layout render."""
    from figma_flutter_agent.generator.cluster_variants import (
        collect_cluster_vector_variants,
        restore_pruned_cluster_vector_keys,
    )
    from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs

    cluster_specs = collect_cluster_widget_specs(
        clean_tree,
        cluster_summary,
        min_count=min_count,
        widget_suffix=widget_suffix,
    )
    if not cluster_specs:
        return None, None
    cluster_classes = {spec.cluster_id: spec.class_name for spec in cluster_specs}
    subtree_specs = collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
    variant_trees: list[CleanDesignTreeNode] = [clean_tree]
    if destination_trees:
        variant_trees.extend(destination_trees.values())
    variant_trees.extend(
        _prepare_subtree_render_root(spec.representative) for spec in subtree_specs
    )
    cluster_vector_variants = collect_cluster_vector_variants(
        variant_trees,
        {spec.cluster_id: spec.representative for spec in cluster_specs},
    )
    restore_pruned_cluster_vector_keys(clean_tree, cluster_vector_variants)
    if destination_trees:
        for destination_tree in destination_trees.values():
            restore_pruned_cluster_vector_keys(destination_tree, cluster_vector_variants)
    return cluster_classes, cluster_vector_variants


def refresh_subtree_widget_planned_files(
    planned: dict[str, str],
    *,
    clean_tree: CleanDesignTreeNode,
    widget_suffix: str,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
) -> dict[str, str]:
    """Re-render subtree widgets when planned bodies are shrink stubs or self-referential."""
    from figma_flutter_agent.generator.planned.reconcile import (
        _is_foreign_delegate_widget_build,
        _is_self_referential_widget_build,
        _is_shrink_only_widget_source,
        preferred_widget_path_for_class,
    )
    from figma_flutter_agent.generator.subtree.plan import (
        _bottom_nav_widget_needs_refresh,
        _collect_subtree_specs_to_render,
        _layout_widget_class_names,
        _resolve_spec_for_layout_widget_class,
    )

    specs = list(collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix))
    if not specs:
        return planned

    merged = dict(planned)
    layout_names = sorted(_layout_widget_class_names(planned))
    to_render = _collect_subtree_specs_to_render(
        merged,
        specs,
        layout_class_names=layout_names,
        clean_tree=clean_tree,
    )
    if not to_render:
        return merged

    started = time.monotonic()
    subtree = render_subtree_widgets(
        to_render,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )
    logger.info(
        "Refreshed {} subtree widget(s) in {:.1f}s (skipped {} valid)",
        len(to_render),
        time.monotonic() - started,
        len(specs) + len(layout_names) - len(to_render),
    )

    def _should_refresh(path: str, class_name: str) -> bool:
        existing = merged.get(path, "")
        if not existing:
            return True
        if _bottom_nav_widget_needs_refresh(existing, class_name):
            return True
        if _is_shrink_only_widget_source(existing):
            return True
        if _is_self_referential_widget_build(existing, class_name):
            return True
        return _is_foreign_delegate_widget_build(existing, class_name)

    def _apply_fresh(spec: SubtreeWidgetSpec, fresh: str) -> None:
        preferred = preferred_widget_path_for_class(spec.class_name)
        if _should_refresh(preferred, spec.class_name):
            merged[preferred] = fresh

    for spec in to_render:
        legacy_path = f"lib/widgets/{spec.file_name}.dart"
        preferred = preferred_widget_path_for_class(spec.class_name)
        fresh = subtree.files.get(legacy_path) or subtree.files.get(preferred)
        if fresh is None:
            continue
        _apply_fresh(spec, fresh)

    for class_name in layout_names:
        preferred = preferred_widget_path_for_class(class_name)
        if not _should_refresh(preferred, class_name):
            continue
        spec = _resolve_spec_for_layout_widget_class(
            class_name,
            specs,
            clean_tree=clean_tree,
        )
        if spec is None:
            continue
        if spec.class_name == class_name:
            legacy_path = f"lib/widgets/{spec.file_name}.dart"
            fresh = subtree.files.get(legacy_path) or subtree.files.get(preferred)
            if fresh is None:
                origin = next((item for item in specs if item.node_id == spec.node_id), None)
                if origin is not None:
                    origin_path = f"lib/widgets/{origin.file_name}.dart"
                    fresh = subtree.files.get(origin_path) or subtree.files.get(
                        preferred_widget_path_for_class(origin.class_name)
                    )
            if fresh is None or spec.class_name not in fresh:
                body = _render_subtree_widget_body(
                    spec.representative,
                    class_name=spec.class_name,
                    uses_svg=uses_svg,
                    cluster_classes=cluster_classes,
                    cluster_vector_variants=cluster_vector_variants,
                )
                fresh = render_widget_file(
                    class_name=spec.class_name,
                    body=body,
                    uses_svg=uses_svg,
                    package_name=package_name,
                    use_package_imports=use_package_imports,
                    source_file=preferred,
                )
            _apply_fresh(spec, fresh)
            continue
        body = _render_subtree_widget_body(
            spec.representative,
            class_name=spec.class_name,
            uses_svg=uses_svg,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
        )
        fresh = render_widget_file(
            class_name=spec.class_name,
            body=body,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            source_file=preferred,
        )
        _apply_fresh(spec, fresh)

    return merged


def _subtree_render_root(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Strip placement stubs so subtree widget files render full bodies."""
    if not node.extracted_widget_ref:
        return node
    return node.model_copy(update={"extracted_widget_ref": None})


def _prepare_subtree_render_root(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Clone a subtree representative and apply the same cluster pruning as layout codegen."""
    from copy import deepcopy

    from figma_flutter_agent.parser.dedup.prune import prune_duplicated_cluster_subtrees
    from figma_flutter_agent.parser.interaction import find_raster_photo_leaf

    root = deepcopy(_subtree_render_root(node))
    if find_raster_photo_leaf(root) is not None:
        return root
    prune_duplicated_cluster_subtrees(root)
    return root


def _subtree_skip_cluster_id_for_root(
    root: CleanDesignTreeNode,
    *,
    class_name: str,
    cluster_classes: dict[str, str] | None,
    cluster_vector_variants: dict | None = None,
) -> str | None:
    """Skip cluster shortcut on the subtree root when the file name differs from the cluster widget."""
    from figma_flutter_agent.generator.layout.widgets import _sizing_like_skip_control

    cluster_id = root.cluster_id
    if not cluster_id or not cluster_classes:
        return None
    mapped = cluster_classes.get(cluster_id)
    if not mapped:
        return None
    if mapped == class_name:
        return cluster_id
    if not root.children and _sizing_like_skip_control(root):
        variant = cluster_vector_variants.get(cluster_id) if cluster_vector_variants else None
        if root.vector_asset_key or variant is not None:
            return None
    return cluster_id


def _render_subtree_widget_body(
    representative: CleanDesignTreeNode,
    *,
    class_name: str,
    uses_svg: bool,
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
    project_dir: Path | None = None,
) -> str:
    """Render a dedicated subtree widget file (inline cluster body, no sibling delegate)."""
    from figma_flutter_agent.generator.layout.widgets.selection import (
        render_compact_trailing_selection_glyph,
    )
    from figma_flutter_agent.generator.variant.state import variant_is_checked
    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_compact_trailing_selection_glyph,
    )
    from figma_flutter_agent.parser.interaction.step import (
        layout_fact_step_indicator_glyph_stack,
        layout_fact_success_check_glyph_host,
    )

    if layout_fact_compact_trailing_selection_glyph(representative):
        return render_compact_trailing_selection_glyph(
            representative,
            selected=variant_is_checked(representative),
        )

    if layout_fact_success_check_glyph_host(representative):
        root = _prepare_subtree_render_root(representative)
        skip_cluster_id = representative.cluster_id if representative.cluster_id else None
        return render_node_body(
            root,
            uses_svg=uses_svg,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
            skip_cluster_id=skip_cluster_id,
        )

    root = _prepare_subtree_render_root(representative)
    force_inline_cluster = (
        layout_fact_step_indicator_glyph_stack(representative)
        or (
            (representative.name or "").strip().lower() == "success"
            and len(representative.children) > 1
        )
    )
    if project_dir is not None and project_dir.is_dir():
        from figma_flutter_agent.parser.boundaries.assets import resolve_missing_image_asset_keys

        resolve_missing_image_asset_keys(root, project_dir)
    from figma_flutter_agent.generator.layout.widgets.thumbnail import try_render_media_avatar_stack

    media_avatar = try_render_media_avatar_stack(root, uses_svg=uses_svg)
    if media_avatar is not None:
        return media_avatar
    if root.type == NodeType.BOTTOM_NAV:
        from figma_flutter_agent.generator.layout.navigation.host import (
            compose_bottom_navigation_host,
        )

        return compose_bottom_navigation_host(root, uses_svg=uses_svg)
    skip_cluster_id = _subtree_skip_cluster_id_for_root(
        root,
        class_name=class_name,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )
    if force_inline_cluster and root.cluster_id:
        skip_cluster_id = root.cluster_id
    body = render_node_body(
        root,
        uses_svg=uses_svg,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        skip_cluster_id=skip_cluster_id,
    )
    from figma_flutter_agent.generator.ir.extracted import (
        _preserve_extracted_widget_decoration_shell,
    )

    return _preserve_extracted_widget_decoration_shell(representative, body)


def render_subtree_widgets(
    specs: list[SubtreeWidgetSpec],
    *,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
    project_dir: Path | None = None,
) -> SubtreeWidgetResult:
    """Render deterministic widget files for vector-rich subtrees."""
    files: dict[str, str] = {}
    for spec in specs:
        body = _render_subtree_widget_body(
            spec.representative,
            class_name=spec.class_name,
            uses_svg=uses_svg,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
            project_dir=project_dir,
        )
        path = f"lib/widgets/{spec.file_name}.dart"
        files[path] = render_widget_file(
            class_name=spec.class_name,
            body=body,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            source_file=path,
        )
    return SubtreeWidgetResult(files=files, specs=tuple(specs))
