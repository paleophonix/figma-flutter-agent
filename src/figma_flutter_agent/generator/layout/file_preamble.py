"""Import and local preamble helpers for layout Dart files."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import to_pascal_case, to_snake_case
from figma_flutter_agent.generator.paths import ImportContext

_TEXT_SCALER_LINE = "    final textScaler = MediaQuery.textScalerOf(context);\n"
_TEXT_WIDGET_MARKERS = ("Text(", "RichText(", "Text.rich(", "TextField(")
_DART_UI_MARKERS = ("BackdropFilter(", "ImageFilter.blur", "Matrix4.")


def body_needs_dart_ui(body: str) -> bool:
    """Return True when generated layout code uses ``dart:ui`` symbols."""
    return any(marker in body for marker in _DART_UI_MARKERS)


def dart_ui_import_line(body: str) -> str:
    """Build ``dart:ui`` import for blur and/or Matrix4 transforms."""
    needs_filter = "ImageFilter" in body or "BackdropFilter" in body
    needs_matrix = "Matrix4." in body
    if not needs_filter and not needs_matrix:
        return ""
    symbols: list[str] = []
    if needs_filter:
        symbols.append("ImageFilter")
    if needs_matrix:
        symbols.append("Matrix4")
    return f"import 'dart:ui' show {', '.join(symbols)};\n\n"


def body_needs_text_scaler(body: str) -> bool:
    """Return True when generated Dart body references text scaler locals."""
    return any(marker in body for marker in _TEXT_WIDGET_MARKERS)


def build_scaler_preamble(body: str) -> str:
    """Return the local text scaler preamble needed by generated text widgets."""
    if body_needs_text_scaler(body):
        return _TEXT_SCALER_LINE
    return ""


def widget_import_lines_for_body(
    body: str,
    *,
    import_context: ImportContext,
    widget_imports: list[str] | None = None,
    cluster_classes: dict[str, str] | None = None,
) -> str:
    """Return ``lib/widgets`` import lines for cluster widgets referenced in *body*.

    Args:
        body: Generated Dart widget expression for a layout or chunk file.
        import_context: Package-relative import resolver for the target file.
        widget_imports: Planned widget file stems (without ``.dart``).
        cluster_classes: ``cluster_id`` to widget class name map from extraction.

    Returns:
        Concatenated import lines, or an empty string when no widgets are referenced.
    """
    stems: set[str] = set()
    if cluster_classes:
        for class_name in set(cluster_classes.values()):
            if f"{class_name}(" in body:
                stems.add(to_snake_case(class_name))
    if widget_imports:
        for stem in widget_imports:
            class_name = to_pascal_case(stem)
            if f"{class_name}(" in body:
                stems.add(stem)
    if not stems:
        return ""
    return "".join(
        f"import '{import_context.uri(f'widgets/{stem}.dart')}';\n" for stem in sorted(stems)
    )
