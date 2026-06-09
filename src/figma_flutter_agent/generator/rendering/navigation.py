"""Router and state-management rendering helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import to_snake_case
from figma_flutter_agent.generator.paths import Architecture, destination_screen_file_path, state_file_path
from figma_flutter_agent.generator.rendering.injections import showcase_provider_name
from figma_flutter_agent.parser.navigation import RouteDefinition
from figma_flutter_agent.parser.transitions import PrototypeTransition


def render_destination_stubs(
    *,
    template: object,
    routes: list[RouteDefinition],
    current_feature: str,
    use_auto_route: bool = False,
    skip_features: set[str] | None = None,
    architecture: Architecture = "feature_first",
) -> dict[str, str]:
    """Render placeholder screens for prototype destination frames."""
    files: dict[str, str] = {}
    current = to_snake_case(current_feature)
    excluded = {current, *(skip_features or set())}
    for route in routes:
        if route.name in excluded:
            continue
        path = destination_screen_file_path(route.name, architecture=architecture)
        files[path] = template.render(
            screen_class=route.screen_class,
            use_auto_route=use_auto_route,
        )
    return files


def render_router_files(
    *,
    env: object,
    routes: list[RouteDefinition],
    routing_type: str,
    initial_route: RouteDefinition | None = None,
    route_transitions: dict[str, PrototypeTransition] | None = None,
) -> dict[str, str]:
    """Render routing bootstrap file for the configured navigation backend."""
    if not routes:
        return {}
    resolved_initial = initial_route or routes[0]
    template_by_type = {
        "go_router": "app_router.dart.j2",
        "auto_route": "app_auto_route.dart.j2",
        "navigator2": "app_navigator2.dart.j2",
    }
    template_name = template_by_type.get(routing_type)
    if template_name is None:
        return {}
    template = env.get_template(template_name)
    files = {
        "lib/core/app_router.dart": template.render(
            routes=routes,
            initial_route=resolved_initial,
            route_transitions=route_transitions or {},
        )
    }
    if routing_type == "auto_route":
        gr_template = env.get_template("app_router.gr.dart.j2")
        files["lib/core/app_router.gr.dart"] = gr_template.render(routes=routes)
    return files


def render_state_management_files(
    *,
    env: object,
    feature_name: str,
    screen_class: str,
    state_type: str,
    architecture: Architecture = "feature_first",
) -> dict[str, str]:
    """Render optional state-management stub files for the primary feature."""
    template_by_type = {
        "riverpod": "state_riverpod.dart.j2",
        "bloc": "state_bloc.dart.j2",
        "provider": "state_provider.dart.j2",
    }
    template_name = template_by_type.get(state_type)
    if template_name is None:
        return {}
    template = env.get_template(template_name)
    path = state_file_path(feature_name, architecture=architecture)
    provider_name = showcase_provider_name(screen_class)
    return {
        path: template.render(
            feature_name=feature_name,
            screen_class=screen_class,
            provider_name=provider_name,
        )
    }
