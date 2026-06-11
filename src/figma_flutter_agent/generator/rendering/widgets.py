"""LLM extracted widget rendering helpers."""

from __future__ import annotations

from typing import TypedDict

from figma_flutter_agent.generator.dart.llm_codegen import (
    _WIDGET_CLASS_RE,
    ensure_valid_llm_widget_code,
    normalize_llm_extracted_widget_code,
    prepare_llm_extracted_widgets,
    sibling_widget_import_uris,
)
from figma_flutter_agent.generator.dart.postprocess import process_generated_dart_source
from figma_flutter_agent.generator.layout.common import to_snake_case
from figma_flutter_agent.generator.paths import ImportContext
from figma_flutter_agent.schemas import ExtractedWidget, FlutterGenerationResponse


class WidgetImport(TypedDict):
    file: str
    widget: ExtractedWidget | None


def prepared_widget_file_stem(
    prepared_code: str,
    *,
    class_to_file: dict[str, str],
    fallback_stem: str,
) -> str:
    """Resolve the ``lib/widgets`` stem for a prepared extracted widget body."""
    match = _WIDGET_CLASS_RE.search(prepared_code)
    if match is None:
        return fallback_stem
    return class_to_file.get(match.group("name"), fallback_stem)


def build_widget_imports(widgets: list[ExtractedWidget]) -> list[WidgetImport]:
    """Build widget import metadata for screen and widget templates."""
    imports: list[WidgetImport] = []
    seen: set[str] = set()
    for widget in widgets:
        file_name = to_snake_case(widget.widget_name)
        if file_name in seen:
            continue
        seen.add(file_name)
        imports.append({"file": file_name, "widget": widget})
    return imports


def render_llm_widget_files(
    *,
    widget_template: object,
    response: FlutterGenerationResponse,
    uses_svg: bool = False,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
) -> dict[str, str]:
    """Render only LLM-extracted widget files without a screen."""
    widget_pairs = [
        (widget.widget_name, widget.resolved_code())
        for widget in response.extracted_widgets
        if widget.resolved_code()
    ]
    prepared_widgets, widget_class_to_file = prepare_llm_extracted_widgets(widget_pairs)
    prepared_by_name = dict(prepared_widgets)
    files: dict[str, str] = {}
    for widget_import in build_widget_imports(response.extracted_widgets):
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
    return files
