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
    if min_value is not None and max_value is not None and max_value < min_value:
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
    return (
        normalized.replace("\\", "\\\\")
        .replace("$", r"\$")
        .replace("\n", "\\n")
        .replace("'", "\\'")
    )


def figma_display_text(node: object) -> str:
    """Return Figma-visible copy with ``textCase`` applied for emit."""
    from figma_flutter_agent.parser.text_case import apply_figma_text_case
    from figma_flutter_agent.schemas import CleanDesignTreeNode

    if not isinstance(node, CleanDesignTreeNode):
        return ""
    raw = node.text or node.name or ""
    return apply_figma_text_case(raw, node.style.text_case)


def escape_figma_text_literal(node: object) -> str:
    """Escape display text for a Dart single-quoted literal."""
    return escape_dart_string(figma_display_text(node))


def node_with_display_accessibility(node: object) -> object:
    """Align accessibility labels with ``textCase`` transforms for TEXT emit."""
    from figma_flutter_agent.parser.text_case import apply_figma_text_case
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

    if not isinstance(node, CleanDesignTreeNode):
        return node
    text_case = node.style.text_case
    if not text_case or text_case == "ORIGINAL":
        return node
    if node.type != NodeType.TEXT:
        return node
    label = node.accessibility_label or node.text or ""
    if not label:
        return node
    display_label = apply_figma_text_case(label, text_case)
    if display_label == label:
        return node
    return node.model_copy(update={"accessibility_label": display_label})


def wrap_repaint_boundary(widget: str) -> str:
    """Isolate repaint for scrollable or heavy subtrees (spec §15)."""
    return f"RepaintBoundary(child: {widget})"


def layout_fact_centered_glyph_badge(node: object) -> bool:
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
    host_centers_child = (
        node.alignment is not None
        and (node.alignment.main or "").lower() == "center"
        and (node.alignment.cross or "").lower() == "center"
    )
    if align != "CENTER" and not host_centers_child:
        return False
    glyph = (text_child.text or "").strip()
    return 0 < len(glyph) <= 3


def is_short_centered_glyph_text(node: object) -> bool:
    """Return True for a single-line centered avatar/badge initial."""
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

    if not isinstance(node, CleanDesignTreeNode) or node.type != NodeType.TEXT:
        return False
    glyph = (node.text or "").strip()
    if not (0 < len(glyph) <= 3):
        return False
    return (node.style.text_align or "").upper() == "CENTER"


ARTBOARD_PREVIEW_WIDTH_DEFINE = "FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH"
ARTBOARD_PREVIEW_HEIGHT_DEFINE = "FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT"
ARTBOARD_CAPTURE_MODE_DEFINE = "FIGMA_FLUTTER_ARTBOARD_CAPTURE_MODE"
ARTBOARD_PREVIEW_CLASS_FIELDS = f"""  static final double _artboardPreviewWidth = double.tryParse(
    const String.fromEnvironment('{ARTBOARD_PREVIEW_WIDTH_DEFINE}'),
  ) ??
      0;
  static final double _artboardPreviewHeight = double.tryParse(
    const String.fromEnvironment('{ARTBOARD_PREVIEW_HEIGHT_DEFINE}'),
  ) ??
      0;
  static final bool _artboardCaptureMode =
      const String.fromEnvironment('{ARTBOARD_CAPTURE_MODE_DEFINE}', defaultValue: '') == '1';
"""
ARTBOARD_PREVIEW_LAYOUT_MARKER = "_artboardPreviewWidth"


def static_artboard_viewport(
    *,
    child: str,
    width_token: str,
    height_token: str,
    alignment: str = "Alignment.topCenter",
) -> str:
    """Bound a root widget to the Figma artboard without responsive host stretch.

    Used for static preview fallbacks when artboard dart-defines are absent so
    ``constraints.maxWidth`` cannot widen phone shells and column roots.
    """
    return (
        f"Align(alignment: {alignment}, "
        f"child: SizedBox(width: {width_token}, height: {height_token}, child: {child}))"
    )


def live_scroll_stack_viewport(
    *,
    stack_widget: str,
    artboard_height_token: str,
) -> str:
    """Emit a scrollable live viewport for absolute stack artboards.

    Replaces uniform ``FittedBox(scaleDown)`` with host-width scroll so padded
    sections can stretch on wide viewports while tall content remains scrollable.
    """
    return (
        "LayoutBuilder("
        "builder: (context, constraints) {"
        f"final viewportHeight = constraints.maxHeight.isFinite && "
        f"constraints.maxHeight > 0 ? constraints.maxHeight : {artboard_height_token};"
        "return SizedBox("
        "width: constraints.maxWidth, "
        "height: viewportHeight, "
        "child: SingleChildScrollView("
        f"child: SizedBox(width: constraints.maxWidth, child: {stack_widget})"
        ")"
        ");"
        "},"
        ")"
    )


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


def wrap_loose_vertical_overflow_child(
    widget: str,
    *,
    alignment: str = "Alignment.topCenter",
    max_height: str | None = None,
) -> str:
    """Loosen vertical flex constraints so text metrics do not trip ``RenderFlex`` overflow.

    Mirrors the positioned-slot law in ``render._wrap_bounded_positioned_slot_child``:
    the outer flex slot keeps its painted bounds while the child lays out at natural
    height (fractional Figma frames vs Flutter ``StrutStyle`` drift).

    When ``max_height`` is set (Figma cross-axis extent), the ``OverflowBox`` is wrapped
    in a finite ``SizedBox`` so ``Expanded`` / scroll hosts cannot pass unbounded height
    (which would size ``RenderConstrainedOverflowBox`` to infinity).
    """
    max_h = max_height if max_height is not None else "double.infinity"
    inner = (
        f"Align(alignment: {alignment}, child: "
        f"OverflowBox(alignment: {alignment}, maxHeight: {max_h}, "
        f"child: {widget}))"
    )
    if max_height is not None:
        return f"SizedBox(height: {max_height}, child: {inner})"
    return inner


def artboard_preview_sized_box(
    *,
    child: str,
    alignment: str = "Alignment.topCenter",
    bounded_child: bool = False,
) -> str:
    """Emit a preview ``SizedBox`` that tolerates fractional artboard height drift.

    Golden capture may pass ``FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT`` rounded to
    whole pixels while the compiled tree keeps fractional heights (e.g. 917.3).
    ``OverflowBox`` prevents ``RenderFlex`` overflow without changing scroll
    behaviour in the non-preview fallback path.

    ``Stack`` roots require finite bounds; pass ``bounded_child=True`` to skip
    ``OverflowBox`` (unbounded ``maxHeight`` crashes ``RenderStack``).
    """
    if bounded_child:
        return (
            "SizedBox("
            "width: previewW, "
            "height: previewH, "
            f"child: Align(alignment: {alignment}, child: {child})"
            ")"
        )
    return (
        "SizedBox("
        "width: previewW, "
        "height: previewH, "
        f"child: Align(alignment: {alignment}, "
        "child: OverflowBox("
        f"alignment: {alignment}, "
        "maxHeight: previewH, "
        f"child: {child}"
        ")))"
    )


def scroll_viewport_child_shell(
    *,
    child: str,
    width_expr: str,
    height_token: str,
    tolerate_metric_drift: bool = False,
    alignment: str = "Alignment.topCenter",
) -> str:
    """Emit a ``SingleChildScrollView`` child shell.

    Standard phone artboards bind width only so scroll content can grow past the
    Figma frame height. Extra-tall artboards may pin height and use
    ``OverflowBox`` for fractional text-metric drift.

    Args:
        child: Dart widget expression laid out inside the shell.
        width_expr: Dart width expression (literal or ``constraints``-derived).
        height_token: Formatted artboard height literal for drift tolerance.
        tolerate_metric_drift: When true, apply ``scroll_artboard_metric_drift_shell``.
        alignment: Alignment for drift-tolerant shells.

    Returns:
        Dart widget expression for the scroll viewport child.
    """
    if tolerate_metric_drift:
        return scroll_artboard_metric_drift_shell(
            child=child,
            width_expr=width_expr,
            height_token=height_token,
            alignment=alignment,
        )
    return f"SizedBox(width: {width_expr}, child: {child})"


def scroll_artboard_metric_drift_shell(
    *,
    child: str,
    width_expr: str,
    height_token: str,
    alignment: str = "Alignment.topCenter",
) -> str:
    """Emit a scroll-child shell that tolerates fractional artboard height drift.

    ``SingleChildScrollView`` hosts pin the Figma artboard height so scroll extent
    matches the design frame. Compiled text metrics can exceed that nominal height
    by sub-pixels; ``OverflowBox`` matches the preview capture law and prevents
    ``RenderFlex`` overflow without dropping the height token.

    Args:
        child: Dart widget expression laid out inside the shell.
        width_expr: Dart width expression (literal or ``constraints``-derived).
        height_token: Formatted artboard height literal for ``SizedBox``/``OverflowBox``.
        alignment: Alignment for ``Align`` and ``OverflowBox``.

    Returns:
        Dart ``SizedBox`` + ``Align`` + ``OverflowBox`` widget expression.
    """
    return (
        f"SizedBox(width: {width_expr}, height: {height_token}, "
        f"child: Align(alignment: {alignment}, "
        "child: OverflowBox("
        f"alignment: {alignment}, "
        f"maxHeight: {height_token}, "
        f"child: {child}"
        ")))"
    )


def artboard_interactive_scroll_preview(*, scroll_child: str) -> str:
    """Emit a scrollable artboard preview for interactive Chrome dev runs.

    Deprecated for wizard static preview — use :func:`artboard_static_wizard_preview`.
    """
    return (
        "SizedBox("
        "width: _artboardPreviewWidth, "
        "height: constraints.maxHeight.isFinite && constraints.maxHeight > 0 "
        "? constraints.maxHeight "
        ": _artboardPreviewHeight, "
        "child: SingleChildScrollView("
        "child: SizedBox("
        "width: _artboardPreviewWidth, "
        "height: _artboardPreviewHeight, "
        f"child: {scroll_child}"
        "))"
        ")"
    )


def artboard_static_wizard_preview(*, scroll_child: str) -> str:
    """Emit a centered, clipped Figma artboard for static wizard Chrome preview.

    Wizard passes artboard dart-defines for ``responsive.mode: static``. The shell
    letterboxes the design inside the browser viewport instead of stretching a
    narrow column across a wide window with a full-bleed white ``Material``.
    """
    return (
        "ColoredBox("
        "color: Color(0xFF1E1E1E), "
        "child: Center("
        "child: ClipRect("
        "child: SizedBox("
        "width: _artboardPreviewWidth, "
        "height: _artboardPreviewHeight, "
        "child: SingleChildScrollView("
        f"child: {scroll_child}"
        ")"
        ")"
        ")"
        ")"
        ")"
    )


def wrap_artboard_preview_layout_builder(
    *,
    preview_child: str,
    fallback: str,
    scroll_child: str | None = None,
) -> str:
    """Emit a ``LayoutBuilder`` that skips ``FittedBox`` margins in artboard preview."""
    preview_body = preview_child.replace("previewW", "_artboardPreviewWidth").replace(
        "previewH", "_artboardPreviewHeight"
    )
    clipped_preview = f"ClipRect(child: {preview_body})"
    interactive_child = scroll_child if scroll_child is not None else preview_body
    static_wizard_preview = artboard_static_wizard_preview(scroll_child=interactive_child)
    return (
        "LayoutBuilder("
        "builder: (context, constraints) {"
        "if (_artboardPreviewWidth > 0 && _artboardPreviewHeight > 0) {"
        "if (_artboardCaptureMode) {"
        f"return {clipped_preview};"
        "}"
        f"return {static_wizard_preview};"
        "}"
        f"return {fallback};"
        "},"
        ")"
    )


GEOMETRY_PLANNER_MARKER = "// <geometry-planner>"
