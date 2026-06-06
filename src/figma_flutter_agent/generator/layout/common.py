"""Shared helpers for deterministic layout code generation."""

from __future__ import annotations

import re

LAZY_CHILD_THRESHOLD = 8

_SNAKE_CASE = re.compile(r"[^a-zA-Z0-9]+")
_FIGMA_KEY_SAFE = re.compile(r"[^A-Za-z0-9_-]")
_DART_TYPE_SAFE = re.compile(r"[^a-zA-Z0-9_]")

_DART_KEYWORDS = frozenset(
    {
        "abstract",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "dynamic",
        "else",
        "enum",
        "export",
        "extends",
        "extension",
        "external",
        "factory",
        "false",
        "final",
        "finally",
        "for",
        "Function",
        "get",
        "hide",
        "if",
        "implements",
        "import",
        "in",
        "interface",
        "is",
        "late",
        "library",
        "mixin",
        "new",
        "null",
        "on",
        "operator",
        "part",
        "required",
        "rethrow",
        "return",
        "set",
        "show",
        "static",
        "super",
        "switch",
        "sync",
        "this",
        "throw",
        "true",
        "try",
        "typedef",
        "var",
        "void",
        "while",
        "with",
        "yield",
    }
)


def sanitize_figma_key_token(node_id: str) -> str:
    """Return a Dart-safe Figma anchor token suffix (whitelist alnum, ``-``, ``_``)."""
    safe = _FIGMA_KEY_SAFE.sub("_", node_id)
    if not safe:
        safe = "unknown"
    if safe[0].isdigit():
        safe = f"n_{safe}"
    return safe


def sanitize_dart_type_name(raw: str) -> str:
    """Return a valid Dart type identifier from arbitrary text."""
    cleaned = _DART_TYPE_SAFE.sub("_", raw.strip())
    if not cleaned:
        return "Feature"
    if cleaned[0].isdigit():
        cleaned = f"N{cleaned}"
    if cleaned in _DART_KEYWORDS:
        cleaned = f"{cleaned}Widget"
    return cleaned


def normalize_box_constraints(
    min_value: float | None,
    max_value: float | None,
) -> tuple[float | None, float | None]:
    """Ensure ``max >= min`` when both bounds are finite."""
    if (
        min_value is not None
        and max_value is not None
        and max_value < min_value
    ):
        return min_value, min_value
    return min_value, max_value


def to_snake_case(value: str) -> str:
    """Convert arbitrary text to snake_case."""
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", normalized)
    parts = [part for part in _SNAKE_CASE.split(normalized) if part]
    return "_".join(part.lower() for part in parts) or "feature"


def to_pascal_case(value: str) -> str:
    """Convert arbitrary text to PascalCase."""
    parts = [part for part in _SNAKE_CASE.split(value) if part]
    pascal = "".join(part.capitalize() for part in parts) or "Feature"
    return sanitize_dart_type_name(pascal)


def to_camel_case(value: str) -> str:
    """Convert arbitrary text to lowerCamelCase."""
    pascal = to_pascal_case(value)
    return pascal[0].lower() + pascal[1:] if len(pascal) > 1 else pascal.lower()


def escape_dart_string(value: str) -> str:
    """Escape a string for single-quoted Dart literals."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\\", "\\\\").replace("\n", "\\n").replace("'", "\\'")


def wrap_repaint_boundary(widget: str) -> str:
    """Isolate repaint for scrollable or heavy subtrees (spec §15)."""
    return f"RepaintBoundary(child: {widget})"


def is_centered_glyph_badge(node: object) -> bool:
    """Return True for square flex hosts carrying one centered glyph (avatar initial)."""
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

    if not isinstance(node, CleanDesignTreeNode):
        return False
    if node.type not in {NodeType.ROW, NodeType.COLUMN, NodeType.CONTAINER}:
        return False
    if len(node.children) != 1 or node.children[0].type != NodeType.TEXT:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width <= 0 or height <= 0:
        return False
    if abs(float(width) - float(height)) > max(4.0, float(width) * 0.08):
        return False
    text_child = node.children[0]
    align = (text_child.style.text_align or "").upper()
    if align != "CENTER":
        return False
    glyph = (text_child.text or "").strip()
    return 0 < len(glyph) <= 3


ARTBOARD_PREVIEW_WIDTH_DEFINE = "FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH"
ARTBOARD_PREVIEW_HEIGHT_DEFINE = "FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT"
ARTBOARD_PREVIEW_CLASS_FIELDS = f"""  static final double _artboardPreviewWidth = double.tryParse(
    const String.fromEnvironment('{ARTBOARD_PREVIEW_WIDTH_DEFINE}'),
  ) ??
      0;
  static final double _artboardPreviewHeight = double.tryParse(
    const String.fromEnvironment('{ARTBOARD_PREVIEW_HEIGHT_DEFINE}'),
  ) ??
      0;
"""
ARTBOARD_PREVIEW_LAYOUT_MARKER = "_artboardPreviewWidth"


def live_scroll_column_viewport(
    *,
    artboard_width_expr: str,
    column_widget: str,
) -> str:
    """Emit a scrollable live viewport for tall column artboards.

    The parent ``GeneratedScreenShell`` already bounds width/height; this keeps
    only ``SingleChildScrollView`` plus a width assignment so content can grow
    taller than the device viewport and stretch on wide web layouts.

    A bounded ``SizedBox`` height is required when ``LayoutBuilder`` receives
    unbounded max height on web; without it ``SingleChildScrollView`` cannot scroll.
    """
    return (
        "SizedBox("
        "height: constraints.maxHeight.isFinite && constraints.maxHeight > 0 "
        "? constraints.maxHeight "
        ": MediaQuery.sizeOf(context).height, "
        "child: SingleChildScrollView("
        f"child: SizedBox(width: {artboard_width_expr}, child: {column_widget})"
        ")"
        ")"
    )


def artboard_preview_sized_box(
    *,
    child: str,
    alignment: str = "Alignment.topCenter",
) -> str:
    """Emit a preview ``SizedBox`` that tolerates fractional artboard height drift.

    Golden capture may pass ``FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT`` rounded to
    whole pixels while the compiled tree keeps fractional heights (e.g. 917.3).
    ``OverflowBox`` prevents ``RenderFlex`` overflow without changing scroll
    behaviour in the non-preview fallback path.
    """
    return (
        "SizedBox("
        "width: previewW, "
        "height: previewH, "
        f"child: Align(alignment: {alignment}, "
        "child: OverflowBox("
        f"alignment: {alignment}, "
        "maxHeight: double.infinity, "
        f"child: {child}"
        ")))"
    )


def wrap_artboard_preview_layout_builder(*, preview_child: str, fallback: str) -> str:
    """Emit a ``LayoutBuilder`` that skips ``FittedBox`` margins in artboard preview."""
    preview_body = preview_child.replace("previewW", "_artboardPreviewWidth").replace(
        "previewH", "_artboardPreviewHeight"
    )
    clipped_preview = f"ClipRect(child: {preview_body})"
    return (
        "LayoutBuilder("
        "builder: (context, constraints) {"
        "if (_artboardPreviewWidth > 0 && _artboardPreviewHeight > 0) {"
        f"return {clipped_preview};"
        "}"
        f"return {fallback};"
        "},"
        ")"
    )


GEOMETRY_PLANNER_MARKER = "// <geometry-planner>"
