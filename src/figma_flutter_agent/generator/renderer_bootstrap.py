"""App bootstrap rendering for Dart code generation."""

from __future__ import annotations

from jinja2 import Environment

from figma_flutter_agent.generator.paths import (
    Architecture,
    ImportContext,
    screen_import_path,
    state_file_path,
)


def render_app_bootstrap(
    env: Environment,
    *,
    feature_name: str,
    screen_class: str,
    app_title: str,
    routing_type: str,
    routing_enabled: bool,
    generate_dark_mode: bool,
    max_web_width: int,
    architecture: Architecture = "feature_first",
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    state_management_type: str = "none",
    theme_variant: str = "material_3",
) -> dict[str, str]:
    """Render the Flutter application entrypoint."""
    template = env.get_template("main.dart.j2")
    import_context = ImportContext(
        package_name=package_name, use_package_imports=use_package_imports
    )
    screen_path = screen_import_path(feature_name, architecture=architecture)
    state_import = None
    if state_management_type == "bloc":
        state_import = import_context.uri(state_file_path(feature_name, architecture=architecture))
    return {
        "lib/main.dart": template.render(
            feature_name=feature_name,
            screen_class=screen_class,
            app_title=app_title,
            routing_type=routing_type,
            routing_enabled=routing_enabled,
            generate_dark_mode=generate_dark_mode,
            max_web_width=max_web_width,
            state_management_type=state_management_type,
            theme_variant=theme_variant,
            theme_import=import_context.uri("theme/app_theme.dart"),
            cupertino_theme_import=import_context.uri("theme/app_cupertino_theme.dart"),
            router_import=import_context.uri("core/app_router.dart"),
            screen_import=import_context.uri(screen_path),
            state_import=state_import,
        )
    }
