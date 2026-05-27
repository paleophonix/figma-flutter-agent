"""Generation file planning extracted from the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.layout_renderer import (
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
    collect_subtree_widget_specs,
    merge_thin_llm_widgets_with_subtrees,
    reconcile_llm_screen_with_subtrees,
    render_subtree_widgets,
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
    uses_svg = any(item.kind == "icon" for item in context.asset_manifest.entries)
    generation_cfg = settings.agent.generation
    package_name = context.package_name
    use_package_imports = generation_cfg.use_package_imports
    state_management_type = settings.agent.state_management.type

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
    subtree_result = None
    if not generation_cfg.use_deterministic_screen:
        subtree_specs = collect_subtree_widget_specs(
            context.clean_tree,
            widget_suffix=settings.agent.naming.widget_suffix,
            reserved_file_names=reserved_widget_names,
        )
        if subtree_specs:
            subtree_result = render_subtree_widgets(
                subtree_specs,
                uses_svg=uses_svg,
                package_name=package_name,
                use_package_imports=use_package_imports,
            )
            planned_files.update(subtree_result.files)

    cluster_classes = cluster_result.cluster_classes if cluster_result else None
    cluster_vector_variants = None
    if cluster_result and cluster_specs:
        from figma_flutter_agent.generator.cluster_variants import collect_cluster_vector_variants

        cluster_vector_variants = collect_cluster_vector_variants(
            [context.clean_tree, *context.destination_trees.values()],
            {spec.cluster_id: spec.representative for spec in cluster_specs},
        )
    widget_import_names = [spec.file_name for spec in cluster_specs] if cluster_specs else None
    deterministic_widget_imports = [spec.file_name for spec in cluster_specs]
    if subtree_result is not None:
        deterministic_widget_imports.extend(spec.file_name for spec in subtree_result.specs)
    deterministic_widget_imports = sorted(set(deterministic_widget_imports))
    architecture = settings.agent.flutter.architecture
    theme_variant = settings.agent.theme.variant

    if settings.agent.theme.generate:
        planned_files.update(
            renderer.render_theme_files(
                context.tokens,
                max_web_width=settings.agent.responsive.max_web_width,
                generate_dark_mode=settings.agent.dark_mode.enabled,
                theme_variant=theme_variant,
            )
        )
    planned_files.update(
        render_layout_file(
            context.clean_tree,
            feature_name=context.resolved_feature,
            uses_svg=uses_svg,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
            widget_imports=widget_import_names,
            package_name=package_name,
            use_package_imports=use_package_imports,
            theme_variant=theme_variant,
            responsive_enabled=settings.agent.responsive.enabled,
            bundled_font_families=frozenset(context.font_manifest.bundled_family_names),
            dart_weight_overrides_by_family=context.font_manifest.dart_weight_overrides_by_family,
        )
    )

    routing_type = settings.agent.routing.type
    use_auto_route = routing_type == "auto_route"
    responsive_enabled = settings.agent.responsive.enabled
    max_web_width = settings.agent.responsive.max_web_width
    primary_routes = build_feature_routes(context.resolved_feature, node_id=context.node_id)
    use_deterministic_screen = generation_cfg.use_deterministic_screen

    classic_absolute = context.clean_tree.type == NodeType.STACK
    responsive_shell = responsive_enabled and not classic_absolute

    if use_deterministic_screen:
        planned_files.update(
            render_deterministic_screen_files(
                feature_name=context.resolved_feature,
                screen_class=primary_routes[0].screen_class,
                uses_svg=uses_svg,
                use_auto_route=use_auto_route,
                responsive_enabled=responsive_shell,
                max_web_width=max_web_width,
                cluster_widget_imports=widget_import_names,
                architecture=architecture,
                package_name=package_name,
                use_package_imports=use_package_imports,
                state_management_type=state_management_type,
                use_scaffold=_resolve_use_scaffold(settings, context.clean_tree),
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
                max_web_width=max_web_width,
                architecture=architecture,
                package_name=package_name,
                use_package_imports=use_package_imports,
                state_management_type=state_management_type,
                extra_widget_imports=extra_widget_imports,
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
                    max_web_width=max_web_width,
                    architecture=architecture,
                    package_name=package_name,
                    use_package_imports=use_package_imports,
                    state_management_type=state_management_type,
                    extra_widget_imports=extra_widget_imports,
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
    if context.generation and not use_deterministic_screen:
        patched_screen_code = reconcile_llm_screen_with_subtrees(
            context.generation.screen_code,
            subtree_result=subtree_result,
            planned_files=planned_files,
            clean_tree=context.clean_tree,
            uses_svg=uses_svg,
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
                    max_web_width=max_web_width,
                    architecture=architecture,
                    package_name=package_name,
                    use_package_imports=use_package_imports,
                    state_management_type=state_management_type,
                    extra_widget_imports=screen_extra_imports or None,
                    screen_only=True,
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

    if settings.agent.validation.generate_golden_test:
        bounds = context.figma_root.get("absoluteBoundingBox") if context.figma_root else None
        surface_width = 390
        surface_height = 844
        if isinstance(bounds, dict):
            if isinstance(bounds.get("width"), (int, float)):
                surface_width = max(int(bounds["width"]), 1)
            if isinstance(bounds.get("height"), (int, float)):
                surface_height = max(int(bounds["height"]), 1)
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

    return reconcile_planned_dart_files(
        planned_files,
        blocked_asset_paths=context.blocked_asset_paths,
    )


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
