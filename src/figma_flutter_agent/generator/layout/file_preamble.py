"""Import and local preamble helpers for layout Dart files."""

from __future__ import annotations

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
