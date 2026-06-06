"""Generation file planning extracted from the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.layout.renderer import (
    render_deterministic_screen_files,
    render_layout_file,
)
from figma_flutter_agent.generator.navigation_codegen import (
    build_prototype_actions,
    build_route_transitions,
)
from figma_flutter_agent.generator.planned_dart import (
    ensure_referenced_widget_imports,
    filter_widget_import_stems,
    reconcile_planned_dart_files,
    widget_import_stems_for_screen,
)
from figma_flutter_agent.generator.renderer import DartRenderer, to_snake_case
from figma_flutter_agent.generator.subtree_widgets import (
    SubtreeWidgetSpec,
    collect_subtree_widget_specs,
    merge_thin_llm_widgets_with_subtrees,
    reconcile_llm_screen_with_subtrees,
)
from figma_flutter_agent.generator.theme_typography import (
    build_text_theme_size_slots,
    build_text_theme_slot_by_style_name,
)
from figma_flutter_agent.generator.widget_extractor import (
    ClusterWidgetSpec,
    collect_cluster_widget_specs,
    render_cluster_widgets,
)
from figma_flutter_agent.parser.navigation import build_feature_routes
from figma_flutter_agent.parser.prototype import PrototypeNavigationPlan
from figma_flutter_agent.parser.tokens import build_design_tokens
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    FontManifest,
    NodeType,
)


def _resolve_use_scaffold(settings: Settings, clean_tree: CleanDesignTreeNode) -> bool:
    """Classic absolute frames are full-bleed; skip Material AppBar unless forced in YAML."""
    if not settings.agent.layout.use_scaffold:
        return False
    return clean_tree.type != NodeType.STACK


def _tree_has_layout_slots(root: CleanDesignTreeNode) -> bool:
    """Return True when any node in ``root`` carries a geometry ``layout_slot``."""
    stack = [root]
    while stack:
        node = stack.pop()
        if node.layout_slot is not None:
            return True
        stack.extend(node.children)
    return False


@dataclass
class GenerationPlanContext:
    """Inputs required to plan generated Dart files without writing them."""

    settings: Settings
    clean_tree: CleanDesignTreeNode
    tokens: DesignTokens
    resolved_feature: str
    node_id: str
    cluster_summary: dict[str, int]
    asset_manifest: AssetManifest = field(default_factory=AssetManifest)
    font_manifest: FontManifest = field(default_factory=FontManifest)
    generation: FlutterGenerationResponse | None = None
    destination_generations: dict[str, FlutterGenerationResponse] = field(default_factory=dict)
    destination_trees: dict[str, CleanDesignTreeNode] = field(default_factory=dict)
    navigation_plan: PrototypeNavigationPlan = field(default_factory=PrototypeNavigationPlan)
    figma_root: dict[str, Any] = field(default_factory=dict)
    routing_on: bool = False
    package_name: str = "demo_app"
    blocked_asset_paths: frozenset[str] = field(default_factory=frozenset)
    skip_screen_post_reconcile: bool = False
    skip_final_reconcile: bool = False
    project_dir: Path | None = None


def plan_generation_files(context: GenerationPlanContext) -> dict[str, str]:
    """Plan all generated Dart files for a pipeline run.

    Args:
        context: Parsed design data, settings, and optional LLM output.

    Returns:
        Mapping of relative project paths to generated file contents.
    """
    settings = context.settings
    renderer = DartRenderer()
    planned_files: dict[str, str] = {}
    uses_svg = any(
        item.asset_path.lower().endswith(".svg")
        for item in context.asset_manifest.entries
    )
    generation_cfg = settings.agent.generation
    package_name = context.package_name
    use_package_imports = generation_cfg.use_package_imports
    state_management_type = settings.agent.state_management.type
    quiet_expected_fallback = settings.agent.runtime.quiet_expected_warnings

    cluster_result = None
    cluster_specs: list[ClusterWidgetSpec] = []
    if generation_cfg.enforce_cluster_widgets and context.cluster_summary:
        cluster_specs = collect_cluster_widget_specs(
            context.clean_tree,
            context.cluster_summary,
            min_count=generation_cfg.cluster_min_count,
            widget_suffix=settings.agent.naming.widget_suffix,
        )
        if cluster_specs:
            clean_trees = [context.clean_tree, *context.destination_trees.values()]
            cluster_result = render_cluster_widgets(
                cluster_specs,
                uses_svg=uses_svg,
                package_name=package_name,
                use_package_imports=use_package_imports,
                clean_trees=clean_trees,
            )
            planned_files.update(cluster_result.files)

    reserved_widget_names = {spec.file_name for spec in cluster_specs}
    subtree_specs: list[SubtreeWidgetSpec] = []
    if not generation_cfg.use_deterministic_screen:
        subtree_specs = collect_subtree_widget_specs(
            context.clean_tree,
            widget_suffix=settings.agent.naming.widget_suffix,
            reserved_file_names=reserved_widget_names,
        )

    from figma_flutter_agent.parser.dedup import (
        prune_decorative_absolute_vectors,
        prune_generation_layout_tree,
    )

    removed_vectors = prune_decorative_absolute_vectors(context.clean_tree)
    if removed_vectors:
        logger.info(
            "Pruned {} decorative absolute Vector node(s) from screen layout tree",
            removed_vectors,
        )
    for destination_tree in context.destination_trees.values():
        prune_decorative_absolute_vectors(destination_tree)

    if generation_cfg.true_subtree_pruning and subtree_specs:
        from figma_flutter_agent.generator.subtree_widgets import (
            replace_extracted_subtree_nodes_with_refs,
        )

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

    cluster_classes = cluster_result.cluster_classes if cluster_result else None
    cluster_vector_variants = None
    if cluster_result and cluster_specs:
        from figma_flutter_agent.generator.cluster_variants import collect_cluster_vector_variants
        from figma_flutter_agent.generator.subtree_widgets import _subtree_render_root

        variant_trees = [context.clean_tree, *context.destination_trees.values()]
        if subtree_specs:
            variant_trees.extend(
                _subtree_render_root(spec.representative) for spec in subtree_specs
            )
        cluster_vector_variants = collect_cluster_vector_variants(
            variant_trees,
            {spec.cluster_id: spec.representative for spec in cluster_specs},
        )
        from figma_flutter_agent.generator.cluster_variants import (
            restore_pruned_cluster_vector_keys,
        )

        restore_pruned_cluster_vector_keys(context.clean_tree, cluster_vector_variants)
        for destination_tree in context.destination_trees.values():
            restore_pruned_cluster_vector_keys(destination_tree, cluster_vector_variants)

    if generation_cfg.use_deterministic_screen and cluster_specs:
        prune_generation_layout_tree(
            context.clean_tree,
            extracted_subtree_node_ids=frozenset(),
        )
        for destination_tree in context.destination_trees.values():
            prune_generation_layout_tree(
                destination_tree,
                extracted_subtree_node_ids=frozenset(),
            )
        if cluster_vector_variants:
            restore_pruned_cluster_vector_keys(context.clean_tree, cluster_vector_variants)
            for destination_tree in context.destination_trees.values():
                restore_pruned_cluster_vector_keys(destination_tree, cluster_vector_variants)

    subtree_result = None
    if subtree_specs:
        from figma_flutter_agent.generator.planned_dart import (
            repair_foreign_delegate_widget_builds,
            repair_stale_widget_ctor_names_in_planned,
        )
        from figma_flutter_agent.generator.subtree_widgets import plan_subtree_widget_files

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
    deterministic_widget_imports = (
        [spec.file_name for spec in cluster_specs] if cluster_specs else []
    )
    if subtree_result is not None:
        from figma_flutter_agent.generator.layout.common import to_snake_case

        deterministic_widget_imports.extend(
            to_snake_case(spec.class_name) for spec in subtree_result.specs
        )
    deterministic_widget_imports = sorted(set(deterministic_widget_imports))
    architecture = settings.agent.flutter.architecture
    theme_variant = settings.agent.theme.variant

    if settings.agent.theme.generate:
        from figma_flutter_agent.generator.renderer_theme import resolve_theme_font_family

        planned_files.update(
            renderer.render_theme_files(
                context.tokens,
                max_web_width=settings.agent.responsive.max_web_width,
                generate_dark_mode=settings.agent.dark_mode.enabled,
                theme_variant=theme_variant,
                primary_font_family=resolve_theme_font_family(
                    context.font_manifest.bundled_family_names,
                ),
            )
        )
    if settings.agent.dev.design_gallery and context.tokens is not None:
        planned_files.update(
            renderer.render_design_gallery_files(
                context.tokens,
                package_name=package_name,
            )
        )
    text_theme_slots = build_text_theme_slot_by_style_name(context.tokens)
    text_theme_size_slots = build_text_theme_size_slots(context.tokens)
    from figma_flutter_agent.generator.normalize import normalize_clean_tree

    unified_canonicalizer = settings.agent.runtime.unified_canonicalizer
    apply_guards = generation_cfg.apply_render_safety_guards
    if unified_canonicalizer or apply_guards:
        context.clean_tree = normalize_clean_tree(
            context.clean_tree,
            tokens=context.tokens,
            project_dir=context.project_dir,
            apply_render_safety=apply_guards,
            use_geometry_planner=generation_cfg.use_geometry_planner,
            strict_geometry_invariants=generation_cfg.strict_geometry_invariants,
        )
        for route_name, destination_tree in list(context.destination_trees.items()):
            context.destination_trees[route_name] = normalize_clean_tree(
                destination_tree,
                tokens=context.tokens,
                project_dir=context.project_dir,
                apply_render_safety=apply_guards,
                use_geometry_planner=generation_cfg.use_geometry_planner,
                strict_geometry_invariants=generation_cfg.strict_geometry_invariants,
            )
        logger.info(
            "plan: canonicalized clean tree(s) (unified={}, render_safety={})",
            unified_canonicalizer,
            apply_guards,
        )
    if generation_cfg.validate_render_safety:
        from figma_flutter_agent.generator.ir.validate import validate_render_safety

        validate_render_safety(context.clean_tree)
        for destination_tree in context.destination_trees.values():
            validate_render_safety(destination_tree)
    skip_layout_reconcile = unified_canonicalizer or apply_guards
    logger.info("plan: generating layout file for {}", context.resolved_feature)
    layout_files = render_layout_file(
        context.clean_tree,
        skip_layout_reconcile=skip_layout_reconcile,
        feature_name=context.resolved_feature,
        uses_svg=uses_svg,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        widget_imports=deterministic_widget_imports or None,
        package_name=package_name,
        use_package_imports=use_package_imports,
        theme_variant=theme_variant,
        responsive_enabled=settings.agent.responsive.enabled,
        snap_device_pixels=settings.agent.layout.snap_device_pixels,
        bundled_font_families=frozenset(context.font_manifest.bundled_family_names),
        dart_weight_overrides_by_family=context.font_manifest.dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slots,
        text_theme_size_slots=text_theme_size_slots,
        de_archetype_pass=settings.agent.runtime.de_archetype_pass,
        use_geometry_planner=generation_cfg.use_geometry_planner,
    )
    if generation_cfg.use_geometry_planner or _tree_has_layout_slots(context.clean_tree):
        from figma_flutter_agent.generator.geometry.invariants import (
            raise_on_hard_geometry_violations,
            validate_geometry_invariants,
        )

        layout_path = f"lib/generated/{context.resolved_feature}_layout.dart"
        layout_source = layout_files.get(layout_path, "")
        emit_violations = validate_geometry_invariants(
            context.clean_tree,
            require_layout_slots=generation_cfg.use_geometry_planner,
            layout_source=layout_source or None,
            strict_invariants=generation_cfg.strict_geometry_invariants,
        )
        raise_on_hard_geometry_violations(emit_violations, context="emit")
    planned_files.update(layout_files)

    routing_type = settings.agent.routing.type
    use_auto_route = routing_type == "auto_route"
    responsive_enabled = settings.agent.responsive.enabled
    max_web_width = settings.agent.responsive.max_web_width
    shell_safe_area = settings.agent.responsive.shell_safe_area
    primary_routes = build_feature_routes(context.resolved_feature, node_id=context.node_id)
    use_deterministic_screen = generation_cfg.use_deterministic_screen
    layout_import_name = f"{context.resolved_feature}_layout"

    responsive_shell = responsive_enabled

    from dataclasses import replace

    from figma_flutter_agent.generator.ir.emitter import (
        IrEmitContext,
        materialize_screen_code_from_ir,
    )

    ir_emit_ctx = IrEmitContext(
        uses_svg=uses_svg,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        theme_variant=theme_variant,
        responsive_enabled=responsive_enabled,
        is_layout_root=True,
        bundled_font_families=frozenset(context.font_manifest.bundled_family_names),
        dart_weight_overrides_by_family=context.font_manifest.dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slots,
        text_theme_size_slots=text_theme_size_slots,
    )

    def _materialize_generation_ir(
        generation: FlutterGenerationResponse | None,
        *,
        clean_tree: CleanDesignTreeNode | None,
        feature_name: str,
    ) -> FlutterGenerationResponse | None:
        if generation is None or clean_tree is None:
            return generation
        has_ir = generation.screen_ir is not None or any(
            widget.widget_ir is not None for widget in generation.extracted_widgets
        )
        if not has_ir:
            return generation
        return materialize_screen_code_from_ir(
            generation,
            clean_tree=clean_tree,
            feature_name=feature_name,
            ctx=ir_emit_ctx,
            use_auto_route=use_auto_route,
            use_scaffold=_resolve_use_scaffold(settings, clean_tree),
            responsive_shell=responsive_shell,
            materialize_screen_body=not use_deterministic_screen,
            project_dir=context.project_dir,
            tokens=context.tokens,
        )

    destination_generations = {
        route_name: _materialize_generation_ir(
            destination_generation,
            clean_tree=context.destination_trees.get(route_name),
            feature_name=route_name,
        )
        or destination_generation
        for route_name, destination_generation in context.destination_generations.items()
    }
    context = replace(
        context,
        generation=_materialize_generation_ir(
            context.generation,
            clean_tree=context.clean_tree,
            feature_name=context.resolved_feature,
        ),
        destination_generations=destination_generations,
    )

    if use_deterministic_screen:
        planned_files.update(
            render_deterministic_screen_files(
                feature_name=context.resolved_feature,
                screen_class=primary_routes[0].screen_class,
                uses_svg=uses_svg,
                use_auto_route=use_auto_route,
                responsive_enabled=responsive_shell,
                shell_safe_area=shell_safe_area,
                max_web_width=max_web_width,
                cluster_widget_imports=deterministic_widget_imports or None,
                architecture=architecture,
                package_name=package_name,
                use_package_imports=use_package_imports,
                state_management_type=state_management_type,
                use_scaffold=_resolve_use_scaffold(settings, context.clean_tree),
                theme_variant=theme_variant,
            )
        )
        if context.generation:
            planned_files.update(
                renderer.render_llm_widget_files(
                    context.generation,
                    uses_svg=uses_svg,
                    package_name=package_name,
                    use_package_imports=use_package_imports,
                )
            )
    elif context.generation:
        extra_widget_imports = deterministic_widget_imports or None
        planned_files.update(
            renderer.render_generation_files(
                context.generation,
                feature_name=context.resolved_feature,
                uses_svg=uses_svg,
                use_auto_route=use_auto_route,
                responsive_enabled=responsive_shell,
                shell_safe_area=shell_safe_area,
                max_web_width=max_web_width,
                layout_import=layout_import_name,
                architecture=architecture,
                package_name=package_name,
                use_package_imports=use_package_imports,
                state_management_type=state_management_type,
                extra_widget_imports=extra_widget_imports,
                quiet_expected_fallback=quiet_expected_fallback,
            )
        )
        for route_name, destination_generation in context.destination_generations.items():
            planned_files.update(
                renderer.render_generation_files(
                    destination_generation,
                    feature_name=route_name,
                    uses_svg=uses_svg,
                    use_auto_route=use_auto_route,
                    responsive_enabled=responsive_shell,
                    shell_safe_area=shell_safe_area,
                    max_web_width=max_web_width,
                    layout_import=f"{route_name}_layout",
                    architecture=architecture,
                    package_name=package_name,
                    use_package_imports=use_package_imports,
                    state_management_type=state_management_type,
                    extra_widget_imports=extra_widget_imports,
                    quiet_expected_fallback=quiet_expected_fallback,
                )
            )

    if context.routing_on and (
        context.generation or use_deterministic_screen or context.navigation_plan.links
    ):
        routes = context.navigation_plan.routes or build_feature_routes(
            context.resolved_feature,
            node_id=context.node_id,
        )
        planned_files.update(
            renderer.render_router_files(
                routes,
                routing_type,
                initial_route=context.navigation_plan.initial_route,
                route_transitions=build_route_transitions(context.navigation_plan),
            )
        )
        prototype_actions = build_prototype_actions(context.navigation_plan)
        planned_files.update(renderer.render_prototype_navigation(prototype_actions, routing_type))
        if context.generation or use_deterministic_screen:
            skip_features = {context.resolved_feature, *context.destination_generations.keys()}
            planned_files.update(
                renderer.render_destination_stubs(
                    routes,
                    current_feature=context.resolved_feature,
                    use_auto_route=use_auto_route,
                    skip_features=skip_features,
                    architecture=architecture,
                )
            )

    if subtree_result is not None:
        planned_files = merge_thin_llm_widgets_with_subtrees(planned_files, subtree_result)
    if subtree_result is not None:
        deterministic_widget_imports = filter_widget_import_stems(
            deterministic_widget_imports,
            planned_files,
        )
    if (
        context.generation
        and not use_deterministic_screen
        and not context.skip_screen_post_reconcile
    ):
        from figma_flutter_agent.generator.llm_dart import apply_safe_screen_code_patch

        patched_screen_code = reconcile_llm_screen_with_subtrees(
            context.generation.screen_code,
            subtree_result=subtree_result,
            planned_files=planned_files,
            clean_tree=context.clean_tree,
            uses_svg=uses_svg,
        )
        from figma_flutter_agent.generator.figma_anchor import inject_figma_keys_into_screen

        patched_screen_code = apply_safe_screen_code_patch(
            patched_screen_code,
            lambda code: inject_figma_keys_into_screen(code, context.clean_tree),
            label="Figma key injection",
        )
        layout_path = f"lib/generated/{context.resolved_feature}_layout.dart"
        layout_source = planned_files.get(layout_path)
        skip_layout_positioned_inject = (
            generation_cfg.use_screen_ir and context.generation.screen_ir is not None
        )
        if layout_source and not skip_layout_positioned_inject:
            from figma_flutter_agent.generator.figma_anchor import (
                companion_dart_sources_for_layout_inject,
                inject_missing_layout_positioned,
            )

            layout_companion_sources = companion_dart_sources_for_layout_inject(
                planned_files,
                layout_path=layout_path,
                generation=context.generation,
            )
            patched_screen_code = apply_safe_screen_code_patch(
                patched_screen_code,
                lambda code: inject_missing_layout_positioned(
                    code,
                    layout_source,
                    context.clean_tree,
                    companion_sources=layout_companion_sources,
                ),
                label="layout Positioned injection",
            )
        if layout_source and context.clean_tree is not None:
            from figma_flutter_agent.generator.llm_dart import apply_clean_tree_text_to_screen

            patched_screen_code = apply_safe_screen_code_patch(
                patched_screen_code,
                lambda code: apply_clean_tree_text_to_screen(code, context.clean_tree),
                label="clean-tree text sync",
            )
        from figma_flutter_agent.generator.figma_anchor import ensure_screen_stack_paint_order

        patched_screen_code = apply_safe_screen_code_patch(
            patched_screen_code,
            ensure_screen_stack_paint_order,
            label="screen stack paint order",
        )
        if patched_screen_code != context.generation.screen_code:
            context.generation = context.generation.model_copy(
                update={"screen_code": patched_screen_code},
            )
            screen_extra_imports = widget_import_stems_for_screen(
                patched_screen_code,
                planned_files,
            )
            planned_files.update(
                renderer.render_generation_files(
                    context.generation,
                    feature_name=context.resolved_feature,
                    uses_svg=uses_svg,
                    use_auto_route=use_auto_route,
                    responsive_enabled=responsive_shell,
                    shell_safe_area=shell_safe_area,
                    max_web_width=max_web_width,
                    layout_import=layout_import_name,
                    architecture=architecture,
                    package_name=package_name,
                    use_package_imports=use_package_imports,
                    state_management_type=state_management_type,
                    extra_widget_imports=screen_extra_imports or None,
                    screen_only=True,
                    quiet_expected_fallback=quiet_expected_fallback,
                )
            )
            planned_files = ensure_referenced_widget_imports(planned_files)

    planned_files.update(
        renderer.render_state_management_files(
            feature_name=context.resolved_feature,
            screen_class=primary_routes[0].screen_class,
            state_type=settings.agent.state_management.type,
            architecture=architecture,
        )
    )

    planned_files.update(
        renderer.render_app_bootstrap(
            feature_name=context.resolved_feature,
            screen_class=primary_routes[0].screen_class,
            app_title=context.clean_tree.name,
            routing_type=routing_type,
            routing_enabled=context.routing_on,
            generate_dark_mode=settings.agent.dark_mode.enabled,
            max_web_width=settings.agent.responsive.max_web_width,
            architecture=architecture,
            package_name=package_name,
            use_package_imports=use_package_imports,
            state_management_type=state_management_type,
            theme_variant=theme_variant,
        )
    )

    bounds = context.figma_root.get("absoluteBoundingBox") if context.figma_root else None
    surface_width = 390
    surface_height = 844
    if isinstance(bounds, dict):
        if isinstance(bounds.get("width"), (int, float)):
            surface_width = max(int(bounds["width"]), 1)
        if isinstance(bounds.get("height"), (int, float)):
            surface_height = max(int(bounds["height"]), 1)
    generation_cfg = settings.agent.generation
    if generation_cfg.llm_visual_refine and not generation_cfg.llm_visual_refine_capture_golden:
        collect_keys = (
            generation_cfg.runtime_geometry_gate
            or generation_cfg.runtime_geometry_capture_if_missing
        )
        planned_files.update(
            renderer.render_capture_test(
                feature_name=context.resolved_feature,
                screen_class=primary_routes[0].screen_class,
                package_name=context.package_name,
                surface_width=surface_width,
                surface_height=surface_height,
                max_web_width=settings.agent.responsive.max_web_width,
                collect_figma_keys=collect_keys,
            )
        )
    if settings.agent.validation.generate_golden_test:
        planned_files.update(
            renderer.render_golden_test(
                feature_name=context.resolved_feature,
                screen_class=primary_routes[0].screen_class,
                package_name=context.package_name,
                surface_width=surface_width,
                surface_height=surface_height,
                max_web_width=settings.agent.responsive.max_web_width,
            )
        )

    if settings.agent.validation.generate_typography_specimen_test:
        planned_files.update(
            renderer.render_typography_specimens_test(
                package_name=context.package_name,
                max_web_width=settings.agent.responsive.max_web_width,
            )
        )

    if context.skip_final_reconcile:
        return planned_files

    logger.info("plan: final planned_dart reconcile")
    reconcile_metadata: dict[str, object] = {}
    reconciled = reconcile_planned_dart_files(
        planned_files,
        blocked_asset_paths=context.blocked_asset_paths,
        typography_tokens=context.tokens,
        package_name=context.package_name,
        clean_tree=context.clean_tree,
        project_dir=context.project_dir,
        widget_suffix=settings.agent.naming.widget_suffix,
        uses_svg=uses_svg,
        use_package_imports=use_package_imports,
        incremental=True,
        cluster_summary=context.cluster_summary,
        cluster_min_count=generation_cfg.cluster_min_count,
        destination_trees=context.destination_trees,
        reconcile_metadata=reconcile_metadata,
    )
    skipped_paths = reconcile_metadata.get("sidecar_skipped_paths", frozenset())
    if isinstance(skipped_paths, frozenset) and skipped_paths:
        from figma_flutter_agent.generator.geometry.invariants import (
            count_violations_by_code,
            raise_on_hard_geometry_violations,
            validate_geometry_invariants,
        )

        layout_path = f"lib/generated/{context.resolved_feature}_layout.dart"
        layout_source = reconciled.get(layout_path, "")
        skip_violations = validate_geometry_invariants(
            context.clean_tree,
            layout_source=layout_source or None,
            sidecar_skipped=True,
            strict_invariants=generation_cfg.strict_geometry_invariants,
        )
        soft = raise_on_hard_geometry_violations(skip_violations, context="ast_coverage")
        if soft:
            reconcile_metadata["geometry_soft_violations"] = count_violations_by_code(soft)
    return reconciled


def plan_from_figma_root(
    root: dict[str, Any],
    settings: Settings,
    *,
    node_id: str = "1:1",
    feature_name: str | None = None,
    package_name: str = "demo_app",
) -> dict[str, str]:
    """Plan deterministic outputs from a local Figma node JSON fixture.

    Args:
        root: Figma frame node dictionary.
        settings: Agent settings controlling generation mode.
        node_id: Node id used for route metadata.
        feature_name: Optional feature folder override.
        package_name: Flutter package name for optional golden test scaffold.

    Returns:
        Planned generated files keyed by relative path.
    """
    tokens = build_design_tokens(root, None)
    clean_tree, _, _, cluster_summary = build_clean_tree(root)
    configured_feature = feature_name or settings.agent.naming.feature_name
    if configured_feature != "auto":
        resolved_feature = to_snake_case(configured_feature)
    else:
        resolved_feature = to_snake_case(clean_tree.name)

    context = GenerationPlanContext(
        settings=settings,
        clean_tree=clean_tree,
        tokens=tokens,
        resolved_feature=resolved_feature,
        node_id=node_id,
        cluster_summary=cluster_summary,
        figma_root=root,
        package_name=package_name,
    )
    return plan_generation_files(context)
