"""Render Dart source files from tokens and LLM output."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from figma_flutter_agent.generator.navigation_codegen import PrototypeAction
from figma_flutter_agent.generator.paths import Architecture
from figma_flutter_agent.generator.renderer_bootstrap import render_app_bootstrap
from figma_flutter_agent.generator.renderer_theme import render_design_gallery, render_theme_files
from figma_flutter_agent.generator.rendering.navigation import (
    render_destination_stubs as render_destination_stub_files,
)
from figma_flutter_agent.generator.rendering.navigation import (
    render_router_files as render_router_dart_files,
)
from figma_flutter_agent.generator.rendering.navigation import (
    render_state_management_files as render_state_files,
)
from figma_flutter_agent.generator.rendering.prototype import (
    render_navigation as render_prototype_navigation_files,
)
from figma_flutter_agent.generator.rendering.prototype import (
    render_scroll_targets as render_prototype_scroll_target_files,
)
from figma_flutter_agent.generator.rendering.screens import (
    render_generation_files as render_screen_generation_files,
)
from figma_flutter_agent.generator.rendering.tests import (
    render_capture_test as render_capture_test_files,
)
from figma_flutter_agent.generator.rendering.tests import (
    render_golden_test as render_golden_test_files,
)
from figma_flutter_agent.generator.rendering.tests import (
    render_typography_specimens_test as render_typography_specimens_test_files,
)
from figma_flutter_agent.generator.rendering.widgets import (
    build_widget_imports,
)
from figma_flutter_agent.generator.rendering.widgets import (
    render_llm_widget_files as render_widget_files,
)
from figma_flutter_agent.parser.navigation import RouteDefinition
from figma_flutter_agent.parser.transitions import PrototypeTransition
from figma_flutter_agent.schemas import (
    DesignTokens,
    FlutterGenerationResponse,
)


class DartRenderer:
    """Render theme, screen, and widget Dart files."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        base = templates_dir or Path(__file__).parent / "templates"
        self._env = Environment(
            loader=FileSystemLoader(str(base)),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._templates_root = base

    def render_theme_files(
        self,
        tokens: DesignTokens,
        *,
        max_web_width: int = 480,
        generate_dark_mode: bool = False,
        theme_variant: str = "material_3",
        primary_font_family: str | None = None,
    ) -> dict[str, str]:
        """Render deterministic theme files from design tokens."""
        return render_theme_files(
            self._env,
            tokens,
            max_web_width=max_web_width,
            generate_dark_mode=generate_dark_mode,
            theme_variant=theme_variant,
            primary_font_family=primary_font_family,
        )

    def render_design_gallery_files(
        self,
        tokens: DesignTokens,
        *,
        package_name: str,
    ) -> dict[str, str]:
        """Render the optional in-app design token gallery screen."""
        return render_design_gallery(self._env, tokens, package_name=package_name)

    def render_generation_files(
        self,
        response: FlutterGenerationResponse,
        *,
        feature_name: str,
        uses_svg: bool = False,
        use_auto_route: bool = False,
        responsive_enabled: bool = True,
        shell_safe_area: bool = False,
        max_web_width: int = 480,
        layout_import: str | None = None,
        extra_widget_imports: list[str] | None = None,
        screen_only: bool = False,
        architecture: Architecture = "feature_first",
        package_name: str = "demo_app",
        use_package_imports: bool = True,
        state_management_type: str = "none",
        quiet_expected_fallback: bool = False,
    ) -> dict[str, str]:
        """Render screen and extracted widget files from LLM output."""
        screen_template = self._env.get_template("screen.dart.j2")
        widget_template = self._env.get_template("widget.dart.j2")
        widget_imports = build_widget_imports(response.extracted_widgets)
        if extra_widget_imports:
            seen = {item["file"] for item in widget_imports}
            for file_name in extra_widget_imports:
                if file_name in seen:
                    continue
                seen.add(file_name)
                widget_imports.append({"file": file_name, "widget": None})
        return render_screen_generation_files(
            screen_template=screen_template,
            widget_template=widget_template,
            response=response,
            widget_imports=widget_imports,
            feature_name=feature_name,
            uses_svg=uses_svg,
            use_auto_route=use_auto_route,
            responsive_enabled=responsive_enabled,
            shell_safe_area=shell_safe_area,
            max_web_width=max_web_width,
            layout_import=layout_import,
            screen_only=screen_only,
            architecture=architecture,
            package_name=package_name,
            use_package_imports=use_package_imports,
            state_management_type=state_management_type,
            quiet_expected_fallback=quiet_expected_fallback,
        )

    def render_llm_widget_files(
        self,
        response: FlutterGenerationResponse,
        *,
        uses_svg: bool = False,
        package_name: str = "demo_app",
        use_package_imports: bool = True,
    ) -> dict[str, str]:
        """Render only LLM-extracted widget files without a screen."""
        widget_template = self._env.get_template("widget.dart.j2")
        return render_widget_files(
            widget_template=widget_template,
            response=response,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
        )

    def render_destination_stubs(
        self,
        routes: list[RouteDefinition],
        *,
        current_feature: str,
        use_auto_route: bool = False,
        skip_features: set[str] | None = None,
        architecture: Architecture = "feature_first",
    ) -> dict[str, str]:
        """Render placeholder screens for prototype destination frames."""
        template = self._env.get_template("destination_screen.dart.j2")
        return render_destination_stub_files(
            template=template,
            routes=routes,
            current_feature=current_feature,
            use_auto_route=use_auto_route,
            skip_features=skip_features,
            architecture=architecture,
        )

    def render_router_files(
        self,
        routes: list[RouteDefinition],
        routing_type: str,
        *,
        initial_route: RouteDefinition | None = None,
        route_transitions: dict[str, PrototypeTransition] | None = None,
    ) -> dict[str, str]:
        """Render routing bootstrap file for the configured navigation backend."""
        return render_router_dart_files(
            env=self._env,
            routes=routes,
            routing_type=routing_type,
            initial_route=initial_route,
            route_transitions=route_transitions,
        )

    def render_golden_test(
        self,
        *,
        feature_name: str,
        screen_class: str,
        package_name: str,
        surface_width: int,
        surface_height: int,
        max_web_width: int,
    ) -> dict[str, str]:
        """Render a Flutter golden test scaffold for the primary screen."""
        template = self._env.get_template("golden_screen_test.dart.j2")
        return render_golden_test_files(
            template=template,
            templates_root=self._templates_root,
            feature_name=feature_name,
            screen_class=screen_class,
            package_name=package_name,
            surface_width=surface_width,
            surface_height=surface_height,
            max_web_width=max_web_width,
        )

    def render_capture_test(
        self,
        *,
        feature_name: str,
        screen_class: str,
        package_name: str,
        surface_width: int,
        surface_height: int,
        max_web_width: int,
        collect_figma_keys: bool,
    ) -> dict[str, str]:
        """Render a lightweight widget test that writes a PNG path from the environment."""
        template = self._env.get_template("capture_screen_test.dart.j2")
        return render_capture_test_files(
            template=template,
            templates_root=self._templates_root,
            feature_name=feature_name,
            screen_class=screen_class,
            package_name=package_name,
            surface_width=surface_width,
            surface_height=surface_height,
            max_web_width=max_web_width,
            collect_figma_keys=collect_figma_keys,
        )

    def render_typography_specimens_test(
        self,
        *,
        package_name: str,
        max_web_width: int,
    ) -> dict[str, str]:
        """Render Flutter golden tests for Table E typography specimens."""
        template = self._env.get_template("typography_specimens_test.dart.j2")
        return render_typography_specimens_test_files(
            template=template,
            package_name=package_name,
            max_web_width=max_web_width,
        )

    def render_app_bootstrap(
        self,
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
        return render_app_bootstrap(
            self._env,
            feature_name=feature_name,
            screen_class=screen_class,
            app_title=app_title,
            routing_type=routing_type,
            routing_enabled=routing_enabled,
            generate_dark_mode=generate_dark_mode,
            max_web_width=max_web_width,
            architecture=architecture,
            package_name=package_name,
            use_package_imports=use_package_imports,
            state_management_type=state_management_type,
            theme_variant=theme_variant,
        )

    def render_state_management_files(
        self,
        *,
        feature_name: str,
        screen_class: str,
        state_type: str,
        architecture: Architecture = "feature_first",
    ) -> dict[str, str]:
        """Render optional state-management stub files for the primary feature."""
        return render_state_files(
            env=self._env,
            feature_name=feature_name,
            screen_class=screen_class,
            state_type=state_type,
            architecture=architecture,
        )

    def render_prototype_scroll_targets(self) -> dict[str, str]:
        """Render scroll target registry used by SCROLL_TO prototype helpers."""
        template = self._env.get_template("prototype_scroll_targets.dart.j2")
        return render_prototype_scroll_target_files(template=template)

    def render_prototype_navigation(
        self,
        actions: list[PrototypeAction],
        routing_type: str,
    ) -> dict[str, str]:
        """Render prototype navigation helper methods for Figma reactions."""
        return render_prototype_navigation_files(
            navigation_template=self._env.get_template("prototype_navigation.dart.j2"),
            scroll_template=self._env.get_template("prototype_scroll_targets.dart.j2"),
            actions=actions,
            routing_type=routing_type,
        )
