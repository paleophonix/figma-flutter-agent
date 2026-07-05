"""Final asset/test scaffolding and reconciliation pass for the planner."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.planned.reconcile import reconcile_planned_dart_files
from figma_flutter_agent.generator.planner.context import GenerationPlanContext
from figma_flutter_agent.generator.renderer import DartRenderer


def render_theme_and_gallery_files(
    context: GenerationPlanContext,
    planned_files: dict[str, str],
    *,
    package_name: str,
    theme_variant: str,
) -> dict[str, str]:
    """Render theme files and the design gallery, if configured.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        planned_files: Mapping of relative project paths to file contents.
        package_name: Flutter package name.
        theme_variant: Configured theme variant.

    Returns:
        Updated mapping of relative project paths to file contents.
    """
    renderer = DartRenderer()
    settings = context.settings

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
    return planned_files


def render_state_and_bootstrap_files(
    context: GenerationPlanContext,
    planned_files: dict[str, str],
    *,
    architecture: str,
    package_name: str,
    use_package_imports: bool,
    state_management_type: str,
    routing_type: str,
    theme_variant: str,
    primary_screen_class: str,
) -> dict[str, str]:
    """Render state management and app bootstrap files.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        planned_files: Mapping of relative project paths to file contents.
        architecture: Configured Flutter architecture.
        package_name: Flutter package name.
        use_package_imports: Whether to emit `package:` imports.
        state_management_type: Configured state management type.
        routing_type: Configured routing type.
        theme_variant: Configured theme variant.
        primary_screen_class: Screen class name of the primary route.

    Returns:
        Updated mapping of relative project paths to file contents.
    """
    renderer = DartRenderer()
    settings = context.settings

    planned_files.update(
        renderer.render_state_management_files(
            feature_name=context.resolved_feature,
            screen_class=primary_screen_class,
            state_type=settings.agent.state_management.type,
            architecture=architecture,
        )
    )
    from figma_flutter_agent.generator.planned.reconcile.bootstrap_refresh import (
        build_planned_bootstrap_context,
        ensure_compiler_bootstrap_planned_files,
        render_planned_bootstrap_files,
    )

    bootstrap_context = build_planned_bootstrap_context(
        settings=settings,
        package_name=package_name,
        feature_name=context.resolved_feature,
        screen_class=primary_screen_class,
        app_title=context.clean_tree.name,
        routing_on=context.routing_on,
    )
    bootstrap_files = render_planned_bootstrap_files(bootstrap_context)
    return ensure_compiler_bootstrap_planned_files(
        planned_files,
        bootstrap_files=bootstrap_files,
        force=True,
        feature_name=context.resolved_feature,
    )


def render_test_scaffolds(
    context: GenerationPlanContext,
    planned_files: dict[str, str],
    *,
    primary_screen_class: str,
) -> dict[str, str]:
    """Render capture, golden, and typography specimen test scaffolds.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        planned_files: Mapping of relative project paths to file contents.
        primary_screen_class: Screen class name of the primary route.

    Returns:
        Updated mapping of relative project paths to file contents.
    """
    renderer = DartRenderer()
    settings = context.settings
    generation_cfg = settings.agent.generation

    from figma_flutter_agent.generator.render_surface import resolve_capture_surface_size

    bounds = context.figma_root.get("absoluteBoundingBox") if context.figma_root else None
    artboard_width = 390
    artboard_height = 844
    if isinstance(bounds, dict):
        if isinstance(bounds.get("width"), (int, float)):
            artboard_width = max(int(bounds["width"]), 1)
        if isinstance(bounds.get("height"), (int, float)):
            artboard_height = max(int(bounds["height"]), 1)
    surface_width, surface_height = resolve_capture_surface_size(
        artboard_width=artboard_width,
        artboard_height=artboard_height,
    )

    if generation_cfg.llm_visual_refine and not generation_cfg.llm_visual_refine_capture_golden:
        collect_keys = (
            generation_cfg.runtime_geometry_gate
            or generation_cfg.runtime_geometry_capture_if_missing
        )
        planned_files.update(
            renderer.render_capture_test(
                feature_name=context.resolved_feature,
                screen_class=primary_screen_class,
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
                screen_class=primary_screen_class,
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
    return planned_files


def run_final_reconcile(
    context: GenerationPlanContext,
    planned_files: dict[str, str],
    *,
    uses_svg: bool,
    use_package_imports: bool,
    cluster_classes: dict[str, str] | None = None,
    cluster_widget_specs: list | None = None,
) -> dict[str, str]:
    """Run the final planned-Dart reconcile pass and geometry soft-checks.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        planned_files: Mapping of relative project paths to file contents.
        uses_svg: Whether the design references SVG assets.
        use_package_imports: Whether to emit `package:` imports.

    Returns:
        Reconciled mapping of relative project paths to file contents, or
        ``planned_files`` unchanged if `context.skip_final_reconcile` is set.
    """
    if context.skip_final_reconcile:
        return planned_files

    settings = context.settings
    generation_cfg = settings.agent.generation

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
        responsive_enabled=settings.agent.responsive.enabled,
        cluster_classes=cluster_classes or context.cluster_classes,
        cluster_widget_specs=cluster_widget_specs or context.cluster_widget_specs or None,
    )
    skipped_paths = reconcile_metadata.get("sidecar_skipped_paths", frozenset())
    if isinstance(skipped_paths, frozenset) and skipped_paths:
        from figma_flutter_agent.generator.geometry.invariants.reporting import (
            count_violations_by_code,
            raise_on_hard_geometry_violations,
        )
        from figma_flutter_agent.generator.geometry.invariants.validate import (
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
