"""IR materialization and screen/router rendering helpers for the planner."""

from __future__ import annotations

from dataclasses import replace

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.materialize import materialize_screen_code_from_ir
from figma_flutter_agent.generator.layout.common import to_pascal_case
from figma_flutter_agent.generator.navigation_codegen import (
    build_prototype_actions,
    build_route_transitions,
)
from figma_flutter_agent.generator.planner.context import (
    GenerationPlanContext,
    _resolve_use_scaffold,
)
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.parser.navigation import build_feature_routes
from figma_flutter_agent.schemas import CleanDesignTreeNode, FlutterGenerationResponse


def _deterministic_layout_screen_response(
    *,
    screen_class: str,
    layout_class: str,
    responsive_shell: bool,
) -> FlutterGenerationResponse:
    body = (
        f"GeneratedScreenShell(child: const {layout_class}())"
        if responsive_shell
        else f"const {layout_class}()"
    )
    return FlutterGenerationResponse(
        screen_code=(
            f"class {screen_class} extends StatelessWidget {{\n"
            f"  const {screen_class}({{super.key}});\n\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            f"    return {body};\n"
            "  }\n"
            "}\n"
        )
    )


def materialize_ir_generations(
    context: GenerationPlanContext,
    *,
    ir_emit_ctx: IrEmitContext,
    use_auto_route: bool,
    responsive_shell: bool,
) -> GenerationPlanContext:
    """Materialize screen code from screen/widget IR for all generations.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        ir_emit_ctx: Shared IR emission context.
        use_auto_route: Whether routing uses `auto_route`.
        responsive_shell: Whether the responsive shell is enabled.

    Returns:
        Updated context with materialized `generation` and
        `destination_generations`.
    """
    settings = context.settings
    static_mode = not settings.agent.responsive.enabled

    def _materialize(
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
        materialized = materialize_screen_code_from_ir(
            generation,
            clean_tree=clean_tree,
            feature_name=feature_name,
            ctx=ir_emit_ctx,
            use_auto_route=use_auto_route,
            use_scaffold=_resolve_use_scaffold(settings, clean_tree),
            responsive_shell=responsive_shell,
            materialize_screen_body=not static_mode,
            project_dir=context.project_dir,
            tokens=context.tokens,
            macro_height_threshold_px=(
                settings.agent.layout_passes.scroll_extent_fallback_threshold_px
                or settings.agent.responsive.macro_height_threshold_px
            ),
            inject_root_scroll_host=(
                settings.agent.layout_passes.inject_root_scroll_host
                and settings.agent.responsive.enabled
            ),
        )
        if not static_mode:
            return materialized
        layout_class = f"{to_pascal_case(feature_name)}Layout"
        screen_class = f"{to_pascal_case(feature_name)}Screen"
        stub = _deterministic_layout_screen_response(
            screen_class=screen_class,
            layout_class=layout_class,
            responsive_shell=False,
        )
        return materialized.model_copy(update={"screen_code": stub.screen_code})

    destination_generations = {
        route_name: _materialize(
            destination_generation,
            clean_tree=context.destination_trees.get(route_name),
            feature_name=route_name,
        )
        or destination_generation
        for route_name, destination_generation in context.destination_generations.items()
    }
    return replace(
        context,
        generation=_materialize(
            context.generation,
            clean_tree=context.clean_tree,
            feature_name=context.resolved_feature,
        ),
        destination_generations=destination_generations,
    )


def render_screen_and_router_files(
    context: GenerationPlanContext,
    planned_files: dict[str, str],
    *,
    uses_svg: bool,
    use_auto_route: bool,
    responsive_shell: bool,
    shell_safe_area: bool,
    max_web_width: int,
    layout_import_name: str,
    architecture: str,
    package_name: str,
    use_package_imports: bool,
    state_management_type: str,
    quiet_expected_fallback: bool,
    deterministic_widget_imports: list[str],
    routing_type: str,
) -> dict[str, str]:
    """Render screen, destination, and router files for the current context.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        planned_files: Mapping of relative project paths to file contents.
        uses_svg: Whether the design references SVG assets.
        use_auto_route: Whether routing uses `auto_route`.
        responsive_shell: Whether the responsive shell is enabled.
        shell_safe_area: Whether the shell wraps content in a safe area.
        max_web_width: Maximum web layout width.
        layout_import_name: Import name of the generated layout file.
        architecture: Configured Flutter architecture.
        package_name: Flutter package name.
        use_package_imports: Whether to emit `package:` imports.
        state_management_type: Configured state management type.
        quiet_expected_fallback: Whether to silence expected fallback warnings.
        deterministic_widget_imports: Widget import stems for the screen.
        routing_type: Configured routing type.

    Returns:
        Updated mapping of relative project paths to file contents.
    """
    renderer = DartRenderer()
    primary_routes = build_feature_routes(context.resolved_feature, node_id=context.node_id)
    primary_screen_class = primary_routes[0].screen_class

    if context.generation:
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
    else:
        planned_files.update(
            renderer.render_generation_files(
                _deterministic_layout_screen_response(
                    screen_class=primary_screen_class,
                    layout_class=f"{to_pascal_case(context.resolved_feature)}Layout",
                    responsive_shell=responsive_shell,
                ),
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
                screen_only=True,
                quiet_expected_fallback=quiet_expected_fallback,
            )
        )

    if context.routing_on and (context.generation or context.navigation_plan.links):
        routes = context.navigation_plan.routes or primary_routes
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
        if context.generation:
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

    return planned_files
