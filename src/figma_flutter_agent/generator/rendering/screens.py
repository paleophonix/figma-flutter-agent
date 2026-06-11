"""LLM screen rendering pipeline."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.llm_codegen import (
    _WIDGET_CLASS_RE,
    ensure_valid_llm_screen_code,
    ensure_valid_llm_widget_code,
    normalize_llm_extracted_widget_code,
    prepare_llm_extracted_widgets,
    reconcile_extracted_widget_references,
    sibling_widget_import_uris,
)
from figma_flutter_agent.generator.dart.postprocess import process_generated_dart_source
from figma_flutter_agent.generator.layout.common import to_pascal_case
from figma_flutter_agent.generator.paths import (
    Architecture,
    ImportContext,
    screen_file_path,
    state_file_path,
)
from figma_flutter_agent.generator.rendering.injections import (
    inject_bloc_builder,
    inject_provider_consumer,
    inject_riverpod_consumer,
    showcase_provider_name,
)
from figma_flutter_agent.generator.rendering.widgets import (
    WidgetImport,
    prepared_widget_file_stem,
)
from figma_flutter_agent.parser.navigation import _screen_class_name
from figma_flutter_agent.schemas import FlutterGenerationResponse


def build_screen_template_imports(
    *,
    import_context: ImportContext,
    layout_import: str | None,
    widget_files: list[str],
    state_type: str,
    feature_name: str,
    architecture: Architecture,
    screen_path: str,
) -> dict[str, object]:
    ctx = ImportContext(
        package_name=import_context.package_name,
        use_package_imports=import_context.use_package_imports,
        source_file=screen_path,
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


def render_generation_files(
    *,
    screen_template: object,
    widget_template: object,
    response: FlutterGenerationResponse,
    widget_imports: list[WidgetImport],
    feature_name: str,
    uses_svg: bool = False,
    use_auto_route: bool = False,
    responsive_enabled: bool = True,
    shell_safe_area: bool = False,
    max_web_width: int = 480,
    layout_import: str | None = None,
    screen_only: bool = False,
    architecture: Architecture = "feature_first",
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    state_management_type: str = "none",
    quiet_expected_fallback: bool = False,
) -> dict[str, str]:
    """Render screen and extracted widget files from LLM output."""
    files: dict[str, str] = {}
    import_context = ImportContext(package_name=package_name, use_package_imports=use_package_imports)
    widget_pairs = [
        (widget.widget_name, widget.resolved_code())
        for widget in response.extracted_widgets
        if widget.resolved_code()
    ]
    prepared_widgets, widget_class_to_file = prepare_llm_extracted_widgets(widget_pairs)
    prepared_by_name = dict(prepared_widgets)

    if not screen_only:
        for widget_import in widget_imports:
            widget = widget_import["widget"]
            if widget is None:
                continue
            prepared_code = prepared_by_name.get(widget.widget_name, widget.resolved_code())
            file_stem = prepared_widget_file_stem(
                prepared_code,
                class_to_file=widget_class_to_file,
                fallback_stem=widget_import["file"],
            )
            widget_file = f"lib/widgets/{file_stem}.dart"
            widget_file_ctx = ImportContext(
                package_name=package_name,
                use_package_imports=use_package_imports,
                source_file=widget_file,
            )
            _, _, own_class = normalize_llm_extracted_widget_code(
                prepared_code,
                widget_name=widget.widget_name,
            )
            match = _WIDGET_CLASS_RE.search(prepared_code)
            if match is not None:
                own_class = match.group("name")
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
            files[widget_file] = process_generated_dart_source(
                rendered,
                package_name=package_name,
            )

    screen_source = response.resolved_screen_code()
    reconciled_screen_code = reconcile_extracted_widget_references(screen_source, widget_pairs)
    layout_class = f"{to_pascal_case(feature_name)}Layout" if layout_import is not None else None
    screen_code = ensure_valid_llm_screen_code(
        reconciled_screen_code,
        strip_generated_shell_class=responsive_enabled,
        expected_screen_class=_screen_class_name(feature_name),
        layout_class=layout_class,
        responsive_enabled=responsive_enabled,
        quiet_expected_fallback=quiet_expected_fallback,
    )
    if use_auto_route:
        screen_code = inject_auto_route(screen_code)
    screen_class_name = extract_screen_class(screen_code)
    if state_management_type == "bloc" and screen_class_name is not None:
        screen_code = inject_bloc_builder(screen_code, screen_class_name)
    elif state_management_type == "riverpod" and screen_class_name is not None:
        screen_code = inject_riverpod_consumer(screen_code, showcase_provider_name(screen_class_name))
    elif state_management_type == "provider" and screen_class_name is not None:
        screen_code = inject_provider_consumer(screen_code, screen_class_name)

    screen_path = screen_file_path(feature_name, architecture=architecture)
    template_imports = build_screen_template_imports(
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
    from figma_flutter_agent.generator.planned.reconcile import (
        _is_large_planned_dart,
        _sanitize_ingested_widget_source,
    )

    if layout_class and f"const {layout_class}()" in screen_code or _is_large_planned_dart(rendered_screen):
        files[screen_path] = _sanitize_ingested_widget_source(
            rendered_screen,
            package_name=package_name,
        )
    else:
        files[screen_path] = process_generated_dart_source(
            rendered_screen,
            package_name=package_name,
        )
    return files


def extract_screen_class(screen_code: str) -> str | None:
    import re

    match = re.search(r"^class\s+\w+", screen_code, re.MULTILINE)
    if match is None:
        return None
    return match.group(0).removeprefix("class ").split()[0]


def inject_auto_route(screen_code: str) -> str:
    """Insert an AutoRoute annotation before the generated screen class."""
    if "@RoutePage" in screen_code:
        return screen_code
    import re

    match = re.search(r"^class\s+\w+", screen_code, re.MULTILINE)
    if match is None:
        return screen_code
    class_decl = match.group(0)
    return screen_code.replace(class_decl, f"@RoutePage()\n{class_decl}", 1)
