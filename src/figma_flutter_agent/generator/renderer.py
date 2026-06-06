"""Render Dart source files from tokens and LLM output."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from figma_flutter_agent.generator.dart.postprocess import process_generated_dart_source
from figma_flutter_agent.generator.layout.common import (
    to_pascal_case,
    to_snake_case,
)
from figma_flutter_agent.generator.llm_dart import (
    ensure_valid_llm_screen_code,
    ensure_valid_llm_widget_code,
    normalize_llm_extracted_widget_code,
    prepare_llm_extracted_widgets,
    reconcile_extracted_widget_references,
    sibling_widget_import_uris,
)

__all__ = [
    "DartRenderer",
    "inject_bloc_builder",
    "inject_provider_consumer",
    "inject_riverpod_consumer",
    "showcase_provider_name",
    "to_pascal_case",
    "to_snake_case",
]
from figma_flutter_agent.generator.navigation_codegen import PrototypeAction, has_scroll_actions
from figma_flutter_agent.generator.paths import (
    Architecture,
    ImportContext,
    destination_screen_file_path,
    screen_file_path,
    state_file_path,
)
from figma_flutter_agent.generator.renderer_bootstrap import render_app_bootstrap
from figma_flutter_agent.generator.renderer_theme import render_design_gallery, render_theme_files
from figma_flutter_agent.parser.navigation import RouteDefinition, _screen_class_name
from figma_flutter_agent.parser.transitions import PrototypeTransition
from figma_flutter_agent.schemas import (
    DesignTokens,
    ExtractedWidget,
    FlutterGenerationResponse,
)

_BUILD_RETURN_RE = re.compile(
    r"(Widget build\(BuildContext context\) \{.*?)(    return .+?;)(\n  \})",
    re.DOTALL,
)


def showcase_provider_name(screen_class: str) -> str:
    """Derive a lowerCamelCase Riverpod provider id from a screen class name."""
    from figma_flutter_agent.generator.layout.common import to_camel_case

    base = screen_class
    if base.endswith("Screen"):
        base = base[: -len("Screen")]
    return f"{to_camel_case(base)}ReadyProvider"


def inject_riverpod_consumer(screen_code: str, provider_name: str) -> str:
    """Wrap the screen build return value in a Riverpod Consumer (showcase wiring)."""
    match = _BUILD_RETURN_RE.search(screen_code)
    if match is None:
        return screen_code
    prefix, return_stmt, suffix = match.groups()
    wrapped_return = (
        "    return Consumer(\n"
        "      builder: (context, ref, _) {\n"
        f"        ref.watch({provider_name});\n"
        f"        {return_stmt.removeprefix('    ')}\n"
        "      },\n"
        "    );"
    )
    return screen_code.replace(prefix + return_stmt + suffix, prefix + wrapped_return + suffix, 1)


def inject_provider_consumer(screen_code: str, screen_class: str) -> str:
    """Wrap the screen build return value with Provider watch (showcase wiring)."""
    match = _BUILD_RETURN_RE.search(screen_code)
    if match is None:
        return screen_code
    prefix, return_stmt, suffix = match.groups()
    wrapped_return = (
        "    return Consumer<"
        f"{screen_class}State>(\n"
        "      builder: (context, state, _) {\n"
        "        if (!state.ready) {\n"
        "          return const SizedBox.shrink();\n"
        "        }\n"
        f"        {return_stmt.removeprefix('    ')}\n"
        "      },\n"
        "    );"
    )
    return screen_code.replace(prefix + return_stmt + suffix, prefix + wrapped_return + suffix, 1)


def inject_bloc_builder(screen_code: str, screen_class: str) -> str:
    """Wrap the screen build return value in a BlocBuilder when bloc is enabled."""
    cubit = f"{screen_class}Cubit"
    state = f"{screen_class}State"
    match = _BUILD_RETURN_RE.search(screen_code)
    if match is None:
        return screen_code
    prefix, return_stmt, suffix = match.groups()
    wrapped_return = (
        "    return BlocBuilder<"
        f"{cubit}, {state}>(\n"
        "      builder: (context, state) {\n"
        f"        {return_stmt.removeprefix('    ')}\n"
        "      },\n"
        "    );"
    )
    return screen_code.replace(prefix + return_stmt + suffix, prefix + wrapped_return + suffix, 1)


_SCREEN_CLASS_RE = re.compile(r"^class\s+\w+", re.MULTILINE)


class _WidgetImport(TypedDict):
    file: str
    widget: ExtractedWidget | None


def _screen_import_context(
    *,
    package_name: str,
    use_package_imports: bool,
    screen_path: str,
) -> ImportContext:
    return ImportContext(
        package_name=package_name,
        use_package_imports=use_package_imports,
        source_file=screen_path,
    )


def _build_screen_template_imports(
    *,
    import_context: ImportContext,
    layout_import: str | None,
    widget_files: list[str],
    state_type: str,
    feature_name: str,
    architecture: Architecture,
    screen_path: str,
) -> dict[str, object]:
    ctx = _screen_import_context(
        package_name=import_context.package_name,
        use_package_imports=import_context.use_package_imports,
        screen_path=screen_path,
    )
    state_import = None
    if state_type != "none":
        state_import = ctx.uri(state_file_path(feature_name, architecture=architecture))
    return {
        "theme_layout_import": ctx.uri("theme/app_layout.dart"),
        "theme_colors_import": ctx.uri("theme/app_colors.dart"),
        "theme_spacing_import": ctx.uri("theme/app_spacing.dart"),
        "layout_import_uri": ctx.uri(f"generated/{layout_import}.dart") if layout_import else None,
        "widget_import_uris": [
            uri
            for file_name in widget_files
            if file_name
            for uri in [ctx.uri(f"widgets/{file_name}.dart")]
            if uri
        ],
        "state_import": state_import,
    }


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
        files: dict[str, str] = {}
        screen_template = self._env.get_template("screen.dart.j2")
        widget_template = self._env.get_template("widget.dart.j2")
        import_context = ImportContext(
            package_name=package_name,
            use_package_imports=use_package_imports,
        )

        widget_imports = self._build_widget_imports(response.extracted_widgets)
        widget_pairs = [
            (widget.widget_name, widget.resolved_code())
            for widget in response.extracted_widgets
            if widget.resolved_code()
        ]
        prepared_widgets, widget_class_to_file = prepare_llm_extracted_widgets(widget_pairs)
        prepared_by_name = dict(prepared_widgets)

        if extra_widget_imports:
            seen = {item["file"] for item in widget_imports}
            for file_name in extra_widget_imports:
                if file_name in seen:
                    continue
                seen.add(file_name)
                widget_imports.append({"file": file_name, "widget": None})

        if not screen_only:
            for widget_import in widget_imports:
                widget = widget_import["widget"]
                if widget is None:
                    continue
                widget_file = f"lib/widgets/{widget_import['file']}.dart"
                widget_file_ctx = ImportContext(
                    package_name=package_name,
                    use_package_imports=use_package_imports,
                    source_file=widget_file,
                )
                prepared_code = prepared_by_name.get(
                    widget.widget_name,
                    widget.resolved_code(),
                )
                _, _, own_class = normalize_llm_extracted_widget_code(
                    prepared_code,
                    widget_name=widget.widget_name,
                )
                sibling_imports = sibling_widget_import_uris(
                    prepared_code,
                    own_class=own_class,
                    class_to_file=widget_class_to_file,
                    uri_for_path=widget_file_ctx.uri,
                )
                rendered = widget_template.render(
                    widget_code=ensure_valid_llm_widget_code(
                        prepared_code,
                        widget_name=widget.widget_name,
                    ),
                    uses_svg=uses_svg,
                    theme_colors_import=widget_file_ctx.uri("theme/app_colors.dart"),
                    theme_spacing_import=widget_file_ctx.uri("theme/app_spacing.dart"),
                    sibling_import_uris=sibling_imports,
                )
                files[widget_file] = process_generated_dart_source(rendered)

        screen_source = response.resolved_screen_code()
        reconciled_screen_code = reconcile_extracted_widget_references(
            screen_source,
            widget_pairs,
        )
        layout_class = (
            f"{to_pascal_case(feature_name)}Layout" if layout_import is not None else None
        )
        screen_code = ensure_valid_llm_screen_code(
            reconciled_screen_code,
            strip_generated_shell_class=responsive_enabled,
            expected_screen_class=_screen_class_name(feature_name),
            layout_class=layout_class,
            responsive_enabled=responsive_enabled,
            quiet_expected_fallback=quiet_expected_fallback,
        )
        if use_auto_route:
            screen_code = self._inject_auto_route(screen_code)
        screen_class_name = self._extract_screen_class(screen_code)
        if state_management_type == "bloc" and screen_class_name is not None:
            screen_code = inject_bloc_builder(screen_code, screen_class_name)
        elif state_management_type == "riverpod" and screen_class_name is not None:
            screen_code = inject_riverpod_consumer(
                screen_code,
                showcase_provider_name(screen_class_name),
            )
        elif state_management_type == "provider" and screen_class_name is not None:
            screen_code = inject_provider_consumer(screen_code, screen_class_name)

        screen_path = screen_file_path(feature_name, architecture=architecture)
        template_imports = _build_screen_template_imports(
            import_context=import_context,
            layout_import=layout_import,
            widget_files=[item["file"] for item in widget_imports],
            state_type=state_management_type,
            feature_name=feature_name,
            architecture=architecture,
            screen_path=screen_path,
        )
        rendered_screen = screen_template.render(
            screen_code=screen_code,
            uses_svg=uses_svg,
            use_auto_route=use_auto_route,
            responsive_enabled=responsive_enabled,
            shell_safe_area=shell_safe_area,
            max_web_width=max_web_width,
            layout_import=layout_import,
            state_management_type=state_management_type,
            **template_imports,
        )
        from figma_flutter_agent.generator.planned_dart import (
            _is_large_planned_dart,
            _sanitize_ingested_widget_source,
        )

        if layout_class and f"const {layout_class}()" in screen_code:
            files[screen_path] = _sanitize_ingested_widget_source(rendered_screen)
        elif _is_large_planned_dart(rendered_screen):
            files[screen_path] = _sanitize_ingested_widget_source(rendered_screen)
        else:
            files[screen_path] = process_generated_dart_source(rendered_screen)
        return files

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
        widget_pairs = [
            (widget.widget_name, widget.resolved_code())
            for widget in response.extracted_widgets
            if widget.resolved_code()
        ]
        prepared_widgets, widget_class_to_file = prepare_llm_extracted_widgets(widget_pairs)
        prepared_by_name = dict(prepared_widgets)
        files: dict[str, str] = {}
        for widget_import in self._build_widget_imports(response.extracted_widgets):
            widget = widget_import["widget"]
            if widget is None:
                continue
            widget_file = f"lib/widgets/{widget_import['file']}.dart"
            widget_file_ctx = ImportContext(
                package_name=package_name,
                use_package_imports=use_package_imports,
                source_file=widget_file,
            )
            prepared_code = prepared_by_name.get(
                widget.widget_name,
                widget.resolved_code(),
            )
            _, _, own_class = normalize_llm_extracted_widget_code(
                prepared_code,
                widget_name=widget.widget_name,
            )
            sibling_imports = sibling_widget_import_uris(
                prepared_code,
                own_class=own_class,
                class_to_file=widget_class_to_file,
                uri_for_path=widget_file_ctx.uri,
            )
            rendered = widget_template.render(
                widget_code=ensure_valid_llm_widget_code(
                    prepared_code,
                    widget_name=widget.widget_name,
                ),
                uses_svg=uses_svg,
                theme_colors_import=widget_file_ctx.uri("theme/app_colors.dart"),
                theme_spacing_import=widget_file_ctx.uri("theme/app_spacing.dart"),
                sibling_import_uris=sibling_imports,
            )
            files[widget_file] = process_generated_dart_source(rendered)
        return files

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

    @staticmethod
    def _build_widget_imports(widgets: list[ExtractedWidget]) -> list[_WidgetImport]:
        """Build widget import metadata for screen and widget templates."""
        imports: list[_WidgetImport] = []
        seen: set[str] = set()
        for widget in widgets:
            file_name = to_snake_case(widget.widget_name)
            if file_name in seen:
                continue
            seen.add(file_name)
            imports.append({"file": file_name, "widget": widget})
        return imports

    @staticmethod
    def _extract_screen_class(screen_code: str) -> str | None:
        match = _SCREEN_CLASS_RE.search(screen_code)
        if match is None:
            return None
        return match.group(0).removeprefix("class ").split()[0]

    @staticmethod
    def _inject_auto_route(screen_code: str) -> str:
        """Insert an AutoRoute annotation before the generated screen class."""
        if "@RoutePage" in screen_code:
            return screen_code
        match = _SCREEN_CLASS_RE.search(screen_code)
        if match is None:
            return screen_code
        class_decl = match.group(0)
        return screen_code.replace(class_decl, f"@RoutePage()\n{class_decl}", 1)

    def render_router_files(
        self,
        routes: list[RouteDefinition],
        routing_type: str,
        *,
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
        template = self._env.get_template(template_name)
        files = {
            "lib/core/app_router.dart": template.render(
                routes=routes,
                initial_route=resolved_initial,
                route_transitions=route_transitions or {},
            )
        }
        if routing_type == "auto_route":
            gr_template = self._env.get_template("app_router.gr.dart.j2")
            files["lib/core/app_router.gr.dart"] = gr_template.render(routes=routes)
        return files

    def _golden_test_harness_dart(self) -> str:
        """Load golden-test harness Dart (``.harness`` avoids IDE analyze in this repo)."""
        harness_path = Path(__file__).parent / "templates" / "element_coordinate_mapper.harness"
        return harness_path.read_text(encoding="utf-8")

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
        golden_file_name = f"../goldens/{feature_name}_screen.png"
        return {
            f"test/golden/{feature_name}_screen_test.dart": template.render(
                feature_name=feature_name,
                screen_class=screen_class,
                package_name=package_name,
                surface_width=surface_width,
                surface_height=surface_height,
                max_web_width=max_web_width,
                golden_file_name=golden_file_name,
            ),
            "test/harness/element_coordinate_mapper.dart": self._golden_test_harness_dart(),
        }

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
        files = {
            f"test/capture/{feature_name}_screen_capture_test.dart": template.render(
                feature_name=feature_name,
                screen_class=screen_class,
                package_name=package_name,
                surface_width=surface_width,
                surface_height=surface_height,
                max_web_width=max_web_width,
                collect_figma_keys=collect_figma_keys,
            ),
        }
        if collect_figma_keys:
            files["test/harness/element_coordinate_mapper.dart"] = self._golden_test_harness_dart()
        return files

    def render_typography_specimens_test(
        self,
        *,
        package_name: str,
        max_web_width: int,
    ) -> dict[str, str]:
        """Render Flutter golden tests for Table E typography specimens."""
        from figma_flutter_agent.validation.specimens import load_font_specimens

        template = self._env.get_template("typography_specimens_test.dart.j2")
        registry = load_font_specimens()
        return {
            "test/golden/typography_specimens_test.dart": template.render(
                package_name=package_name,
                max_web_width=max_web_width,
                specimens=registry.specimens,
            )
        }

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
        template_by_type = {
            "riverpod": "state_riverpod.dart.j2",
            "bloc": "state_bloc.dart.j2",
            "provider": "state_provider.dart.j2",
        }
        template_name = template_by_type.get(state_type)
        if template_name is None:
            return {}
        template = self._env.get_template(template_name)
        path = state_file_path(feature_name, architecture=architecture)
        provider_name = showcase_provider_name(screen_class)
        return {
            path: template.render(
                feature_name=feature_name,
                screen_class=screen_class,
                provider_name=provider_name,
            )
        }

    def render_prototype_scroll_targets(self) -> dict[str, str]:
        """Render scroll target registry used by SCROLL_TO prototype helpers."""
        template = self._env.get_template("prototype_scroll_targets.dart.j2")
        return {"lib/core/prototype_scroll_targets.dart": template.render()}

    def render_prototype_navigation(
        self,
        actions: list[PrototypeAction],
        routing_type: str,
    ) -> dict[str, str]:
        """Render prototype navigation helper methods for Figma reactions."""
        if not actions:
            return {}
        template = self._env.get_template("prototype_navigation.dart.j2")
        files = {
            "lib/core/prototype_navigation.dart": template.render(
                actions=actions,
                routing_type=routing_type,
                has_scroll_actions=has_scroll_actions(actions),
            )
        }
        if has_scroll_actions(actions):
            files.update(self.render_prototype_scroll_targets())
        return files
