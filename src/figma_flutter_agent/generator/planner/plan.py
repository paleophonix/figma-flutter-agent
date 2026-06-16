"""Core planning functions for Dart file generation."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.layout import (
    render_layout_file,
)
from figma_flutter_agent.generator.planner.cluster_subtree import (
    apply_true_subtree_pruning,
    build_deterministic_widget_imports,
    collect_and_restore_cluster_vector_variants,
    plan_subtree_widgets,
    prune_decorative_vectors,
)
from figma_flutter_agent.generator.planner.context import (
    GenerationPlanContext,
    _tree_has_layout_slots,
)
from figma_flutter_agent.generator.planner.finalize import (
    render_state_and_bootstrap_files,
    render_test_scaffolds,
    render_theme_and_gallery_files,
    run_final_reconcile,
)
from figma_flutter_agent.generator.planner.ir_render import (
    materialize_ir_generations,
    render_screen_and_router_files,
)
from figma_flutter_agent.generator.planner.screen_reconcile import (
    merge_subtree_results,
    reconcile_screen_code_with_layout,
)
from figma_flutter_agent.generator.subtree import (
    SubtreeWidgetSpec,
    collect_subtree_widget_specs,
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


def plan_generation_files(context: GenerationPlanContext) -> dict[str, str]:
    """Plan all generated Dart files for a pipeline run.

    Args:
        context: Parsed design data, settings, and optional LLM output.

    Returns:
        Mapping of relative project paths to generated file contents.
    """
    settings = context.settings
    planned_files: dict[str, str] = {}
    from figma_flutter_agent.debug.provenance import set_visual_pixel_mutation_enforcement
    from figma_flutter_agent.generator.visual.renderer import should_use_visual_renderer

    set_visual_pixel_mutation_enforcement(should_use_visual_renderer(settings))
    uses_svg = any(
        item.asset_path.lower().endswith(".svg") for item in context.asset_manifest.entries
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
                project_dir=context.project_dir,
            )
            planned_files.update(cluster_result.files)

    reserved_widget_names = {spec.file_name for spec in cluster_specs}
    subtree_specs: list[SubtreeWidgetSpec] = []
    subtree_specs = collect_subtree_widget_specs(
        context.clean_tree,
        widget_suffix=settings.agent.naming.widget_suffix,
        reserved_file_names=reserved_widget_names,
    )

    prune_decorative_vectors(context)
    apply_true_subtree_pruning(context, subtree_specs)

    cluster_classes = cluster_result.cluster_classes if cluster_result else None
    cluster_vector_variants = collect_and_restore_cluster_vector_variants(
        context,
        cluster_specs,
        subtree_specs,
        cluster_result,
    )

    planned_files, subtree_result = plan_subtree_widgets(
        context,
        planned_files,
        subtree_specs,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )
    deterministic_widget_imports = build_deterministic_widget_imports(cluster_specs, subtree_result)
    architecture = settings.agent.flutter.architecture
    theme_variant = settings.agent.theme.variant

    planned_files = render_theme_and_gallery_files(
        context,
        planned_files,
        package_name=package_name,
        theme_variant=theme_variant,
    )
    text_theme_slots = build_text_theme_slot_by_style_name(context.tokens)
    text_theme_size_slots = build_text_theme_size_slots(context.tokens)
    from figma_flutter_agent.generator.normalize import normalize_clean_tree

    unified_canonicalizer = settings.agent.runtime.unified_canonicalizer
    apply_guards = generation_cfg.apply_render_safety_guards
    if unified_canonicalizer or apply_guards:
        main_screen_ir = (
            context.generation.screen_ir
            if context.generation is not None and context.generation.screen_ir is not None
            else None
        )
        context.clean_tree = normalize_clean_tree(
            context.clean_tree,
            tokens=context.tokens,
            project_dir=context.project_dir,
            screen_ir=main_screen_ir,
            apply_render_safety=apply_guards,
            use_geometry_planner=generation_cfg.use_geometry_planner,
            strict_geometry_invariants=generation_cfg.strict_geometry_invariants,
            preserve_placement=generation_cfg.preserve_placement,
            suppress_archetype_compensation=generation_cfg.suppress_archetype_compensation,
            archetype_reconcile=generation_cfg.archetype_reconcile,
        )
        for route_name, destination_tree in list(context.destination_trees.items()):
            dest_generation = context.destination_generations.get(route_name)
            dest_screen_ir = (
                dest_generation.screen_ir
                if dest_generation is not None and dest_generation.screen_ir is not None
                else None
            )
            context.destination_trees[route_name] = normalize_clean_tree(
                destination_tree,
                tokens=context.tokens,
                project_dir=context.project_dir,
                screen_ir=dest_screen_ir,
                apply_render_safety=apply_guards,
                use_geometry_planner=generation_cfg.use_geometry_planner,
                strict_geometry_invariants=generation_cfg.strict_geometry_invariants,
                preserve_placement=generation_cfg.preserve_placement,
                suppress_archetype_compensation=generation_cfg.suppress_archetype_compensation,
                archetype_reconcile=generation_cfg.archetype_reconcile,
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
    from figma_flutter_agent.generator.ir.passes.planner import (
        apply_layout_passes_to_context,
    )

    context = apply_layout_passes_to_context(context)
    if generation_cfg.use_geometry_planner:
        from figma_flutter_agent.generator.normalize import replan_geometry_after_layout_passes

        context.clean_tree = replan_geometry_after_layout_passes(
            context.clean_tree,
            project_dir=context.project_dir,
        )
        for route_name, destination_tree in list(context.destination_trees.items()):
            context.destination_trees[route_name] = replan_geometry_after_layout_passes(
                destination_tree,
                project_dir=context.project_dir,
            )
    if context.project_dir is not None:
        from figma_flutter_agent.debug.responsiveness import write_responsiveness_report

        write_responsiveness_report(
            feature_name=context.resolved_feature,
            clean_tree=context.clean_tree,
            project_dir=context.project_dir,
        )
    from figma_flutter_agent.generator.normalize import clear_extracted_refs_for_inline_hosts

    if context.generation is not None and context.generation.screen_ir is not None:
        from figma_flutter_agent.generator.ir.presence import sanitize_screen_ir_extracted_refs

        extracted_names = frozenset(
            widget.widget_name for widget in (context.generation.extracted_widgets or [])
        )
        sanitize_screen_ir_extracted_refs(
            context.generation.screen_ir,
            context.clean_tree,
            extracted_widget_names=extracted_names,
            widget_suffix=settings.agent.naming.widget_suffix,
        )
    context.clean_tree = clear_extracted_refs_for_inline_hosts(context.clean_tree)
    for route_name, destination_tree in list(context.destination_trees.items()):
        context.destination_trees[route_name] = clear_extracted_refs_for_inline_hosts(
            destination_tree
        )
    if context.truth_snapshot is not None:
        from figma_flutter_agent.parser.truth_snapshot import attach_emit_tree

        context.truth_emit_pair = attach_emit_tree(
            context.truth_snapshot,
            context.clean_tree,
        )
    logger.info("plan: generating layout file for {}", context.resolved_feature)
    from figma_flutter_agent.generator.visual.renderer import (
        render_visual_layout_files,
        should_use_visual_renderer,
    )

    layout_screen_ir = (
        context.generation.screen_ir
        if context.generation is not None and context.generation.screen_ir is not None
        else None
    )
    layout_render_kwargs = dict(
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
        de_archetype_pass=settings.agent.runtime.de_archetype_pass
        or generation_cfg.suppress_archetype_compensation,
        archetype_reconcile=generation_cfg.archetype_reconcile
        and not generation_cfg.suppress_archetype_compensation,
        use_geometry_planner=generation_cfg.use_geometry_planner,
        skip_layout_reconcile=skip_layout_reconcile,
        screen_ir=layout_screen_ir,
    )
    if should_use_visual_renderer(settings):
        layout_files = render_visual_layout_files(
            context.clean_tree,
            settings=settings,
            truth_snapshot=context.truth_snapshot,
            **layout_render_kwargs,
        )
    else:
        layout_files = render_layout_file(context.clean_tree, **layout_render_kwargs)
    if generation_cfg.use_geometry_planner or _tree_has_layout_slots(context.clean_tree):
        from figma_flutter_agent.generator.geometry.invariants.reporting import (
            raise_on_hard_geometry_violations,
        )
        from figma_flutter_agent.generator.geometry.invariants.validate import (
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
    if settings.agent.ux.write_report and context.project_dir is not None:
        layout_path = f"lib/generated/{context.resolved_feature}_layout.dart"
        layout_source = layout_files.get(layout_path, "")
        if layout_source:
            from figma_flutter_agent.parser.ux_report import augment_ai_ux_report_layout_tier

            augment_ai_ux_report_layout_tier(
                context.project_dir,
                context.resolved_feature,
                layout_source=layout_source,
                root=context.clean_tree,
                responsive_enabled=settings.agent.responsive.enabled,
            )

    routing_type = settings.agent.routing.type
    use_auto_route = routing_type == "auto_route"
    responsive_enabled = settings.agent.responsive.enabled
    max_web_width = settings.agent.responsive.max_web_width
    shell_safe_area = settings.agent.responsive.shell_safe_area
    primary_routes = build_feature_routes(context.resolved_feature, node_id=context.node_id)
    layout_import_name = f"{context.resolved_feature}_layout"

    responsive_shell = responsive_enabled

    semantics = settings.agent.semantics
    generation_cfg = settings.agent.generation
    strict_fidelity = (
        semantics.strict_fidelity or generation_cfg.strict_visual_fidelity
    )
    strict_l10n = semantics.strict_l10n or generation_cfg.strict_product_fidelity
    strict_a11y = semantics.strict_a11y or generation_cfg.strict_product_fidelity
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
        semantic_report_only=semantics.report_only,
        semantics=semantics,
        strict_fidelity=strict_fidelity,
        strict_l10n=strict_l10n,
        strict_a11y=strict_a11y,
        strict_contrast=settings.agent.quality.strict_contrast,
    )
    context = materialize_ir_generations(
        context,
        ir_emit_ctx=ir_emit_ctx,
        use_auto_route=use_auto_route,
        responsive_shell=responsive_shell,
    )
    planned_files = render_screen_and_router_files(
        context,
        planned_files,
        uses_svg=uses_svg,
        use_auto_route=use_auto_route,
        responsive_shell=responsive_shell,
        shell_safe_area=shell_safe_area,
        max_web_width=max_web_width,
        layout_import_name=layout_import_name,
        architecture=architecture,
        package_name=package_name,
        use_package_imports=use_package_imports,
        state_management_type=state_management_type,
        quiet_expected_fallback=quiet_expected_fallback,
        deterministic_widget_imports=deterministic_widget_imports,
        routing_type=routing_type,
    )

    planned_files, deterministic_widget_imports = merge_subtree_results(
        context,
        planned_files,
        subtree_result,
        deterministic_widget_imports,
    )
    planned_files = reconcile_screen_code_with_layout(
        context,
        planned_files,
        subtree_result=subtree_result,
        uses_svg=uses_svg,
        use_auto_route=use_auto_route,
        responsive_shell=responsive_shell,
        shell_safe_area=shell_safe_area,
        max_web_width=max_web_width,
        layout_import_name=layout_import_name,
        architecture=architecture,
        package_name=package_name,
        use_package_imports=use_package_imports,
        state_management_type=state_management_type,
        quiet_expected_fallback=quiet_expected_fallback,
    )

    planned_files = run_final_reconcile(
        context,
        planned_files,
        uses_svg=uses_svg,
        use_package_imports=use_package_imports,
    )
    planned_files = render_state_and_bootstrap_files(
        context,
        planned_files,
        architecture=architecture,
        package_name=package_name,
        use_package_imports=use_package_imports,
        state_management_type=state_management_type,
        routing_type=routing_type,
        theme_variant=theme_variant,
        primary_screen_class=primary_routes[0].screen_class,
    )
    from figma_flutter_agent.debug.provenance import write_provenance_dump

    write_provenance_dump()
    return render_test_scaffolds(
        context,
        planned_files,
        primary_screen_class=primary_routes[0].screen_class,
    )
