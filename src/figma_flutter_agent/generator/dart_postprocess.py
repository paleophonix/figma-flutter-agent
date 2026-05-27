"""Post-processing helpers for generated Dart sources."""

from __future__ import annotations

import re

from loguru import logger

_TEXT_SCALER_DECL_RE = re.compile(
    r"(textScaler:\s*MediaQuery\.textScalerOf\(\w+\)|"
    r"(?:final|var)\s+\w*\s*textScaler\s*=\s*MediaQuery\.textScalerOf\(\w+\))"
)
_BUILD_CONTEXT_PARAM_RE = re.compile(r"BuildContext\s+(?P<context>\w+)")
_TEXT_DISPLAY_WIDGET_RE = re.compile(
    r"(?<!TextStyle)\b(?:Text(?:\.rich)?|SelectableText|EditableText)\s*\("
)
TEXT_DISPLAY_WIDGET_RE = _TEXT_DISPLAY_WIDGET_RE
_TEXT_WIDGET_RE = _TEXT_DISPLAY_WIDGET_RE
_BUILD_METHOD_RE = re.compile(r"Widget\s+build\s*\(\s*BuildContext\s+(?P<context>\w+)\s*\)\s*\{")
_HELPER_METHOD_SIGNATURE_RE = re.compile(
    r"(?P<ret>\w+)\s+(?P<name>_\w+)\s*\((?P<params>[^)]*)\)\s*(?:async\s*)?\{"
)
_CONTEXT_REFERENCE_RE = re.compile(
    r"\b(?:Theme|MediaQuery|Navigator|Scaffold|DefaultTextStyle)\.of\(context\)"
    r"|\bMediaQuery\.textScalerOf\(context\)"
)
_CONST_BEFORE_TEXT_RE = re.compile(r"\bconst\s*$")
_MISUSED_ALIGNMENT_PARAM_RE = re.compile(
    r"(?P<param>alignment|crossAxisAlignment|mainAxisAlignment)\s*:"
    r"\s*Alignment\.(?P<member>start|end|center|stretch|spaceBetween|spaceAround|spaceEvenly|"
    r"topStart|topEnd|bottomStart|bottomEnd|centerStart|centerEnd|left|right)\b"
)
_INVALID_ALIGNMENT_RE = re.compile(
    r"\bAlignment\.(start|end|topStart|topEnd|bottomStart|bottomEnd|centerStart|centerEnd|left|right|center)\b"
)
_MISUSED_TEXT_ALIGN_WIDGET_RE = re.compile(
    r"textAlign:\s*(?!(?:TextAlign\.))(?P<align>Center|Left|Right|Start|End|Justify)\b"
)
_MISUSED_TRANSFORM_ORIGIN_ALIGNMENT_RE = re.compile(
    r"origin:\s*Alignment\.(\w+)"
)
_ALIGN_WIDGET_REPLACEMENTS = {
    "start": "AlignmentDirectional.centerStart",
    "end": "AlignmentDirectional.centerEnd",
    "topStart": "AlignmentDirectional.topStart",
    "topEnd": "AlignmentDirectional.topEnd",
    "bottomStart": "AlignmentDirectional.bottomStart",
    "bottomEnd": "AlignmentDirectional.bottomEnd",
    "centerStart": "AlignmentDirectional.centerStart",
    "centerEnd": "AlignmentDirectional.centerEnd",
    "center": "Alignment.center",
    "left": "Alignment.centerLeft",
    "right": "Alignment.centerRight",
}
_CROSS_AXIS_REPLACEMENTS = {
    "start": "CrossAxisAlignment.start",
    "end": "CrossAxisAlignment.end",
    "center": "CrossAxisAlignment.center",
    "stretch": "CrossAxisAlignment.stretch",
    "topStart": "CrossAxisAlignment.start",
    "topEnd": "CrossAxisAlignment.end",
    "bottomStart": "CrossAxisAlignment.start",
    "bottomEnd": "CrossAxisAlignment.end",
    "centerStart": "CrossAxisAlignment.start",
    "centerEnd": "CrossAxisAlignment.end",
    "left": "CrossAxisAlignment.start",
    "right": "CrossAxisAlignment.end",
}
_MAIN_AXIS_REPLACEMENTS = {
    "start": "MainAxisAlignment.start",
    "end": "MainAxisAlignment.end",
    "center": "MainAxisAlignment.center",
    "spaceBetween": "MainAxisAlignment.spaceBetween",
    "spaceAround": "MainAxisAlignment.spaceAround",
    "spaceEvenly": "MainAxisAlignment.spaceEvenly",
    "topStart": "MainAxisAlignment.start",
    "topEnd": "MainAxisAlignment.end",
    "bottomStart": "MainAxisAlignment.start",
    "bottomEnd": "MainAxisAlignment.end",
    "centerStart": "MainAxisAlignment.start",
    "centerEnd": "MainAxisAlignment.end",
    "left": "MainAxisAlignment.start",
    "right": "MainAxisAlignment.end",
}

_GESTURE_DETECTOR_PARAM_FIXES: dict[str, str] = {
    "horizontalDragStart": "onHorizontalDragStart",
    "horizontalDragUpdate": "onHorizontalDragUpdate",
    "horizontalDragEnd": "onHorizontalDragEnd",
    "verticalDragStart": "onVerticalDragStart",
    "verticalDragUpdate": "onVerticalDragUpdate",
    "verticalDragEnd": "onVerticalDragEnd",
    "panStart": "onPanStart",
    "panUpdate": "onPanUpdate",
    "panEnd": "onPanEnd",
}

_ICON_GETTER_REPLACEMENTS: dict[str, str] = {
    "forward_15_rounded": "forward_10",
    "replay_15_rounded": "replay_10",
    "forward_15": "forward_10",
    "replay_15": "replay_10",
}
_DART_MATH_MIN_RE = re.compile(r"(?<!math\.)(?<![.\w])min\s*\(")
_DART_MATH_MAX_RE = re.compile(r"(?<!math\.)(?<![.\w])max\s*\(")
_FONT_WEIGHT_RE = re.compile(r"FontWeight\.w(\d+)")
_VALID_FONT_WEIGHTS = frozenset({100, 200, 300, 400, 500, 600, 700, 800, 900})
_TIMER_USAGE_RE = re.compile(r"\bTimer(?:\?|[\.(\s]|;|$)")
_INVALID_LLM_NAMED_PARAMS = (
    "failOverErrorResolvers",
    "failOnError",
)
_MALFORMED_EMPTY_CLOSURE_COMMA_RE = re.compile(r"\(\)\s*\{,")
_TAP_GESTURE_RECOGNIZER_RE = re.compile(r"\bTapGestureRecognizer\b")
_BUTTON_WIDGETS = (
    "ElevatedButton",
    "TextButton",
    "FilledButton",
    "OutlinedButton",
    "IconButton",
)
_WIDGET_CLASS_RE = re.compile(
    r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)
_REQUIRED_ON_PRESSED_RE = re.compile(
    r"required\s+(?:this\.)?onPressed\b|required\s+VoidCallback\s+onPressed\b"
)


def discover_widgets_requiring_on_pressed(sources: dict[str, str]) -> tuple[str, ...]:
    """Return widget class names that declare a required ``onPressed`` parameter."""
    names: list[str] = []
    for path, content in sources.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/") or not normalized.endswith(".dart"):
            continue
        if _REQUIRED_ON_PRESSED_RE.search(content) is None:
            continue
        match = _WIDGET_CLASS_RE.search(content)
        if match is not None:
            names.append(match.group("name"))
    return tuple(dict.fromkeys(names))


def ensure_required_on_pressed_callbacks(
    source: str,
    *,
    widget_names: tuple[str, ...],
) -> str:
    """Inject no-op ``onPressed`` for custom widgets that require it."""
    updated = source
    for widget_name in widget_names:
        updated = _ensure_widget_has_on_pressed(updated, widget_name)
    return updated


def postprocess_generated_dart(source: str, *, include_text_scaler: bool = True) -> str:
    """Apply deterministic fixes to LLM-generated Dart before validation/write.

    Args:
        source: Raw or templated Dart widget or screen source.
        include_text_scaler: When False, skip text-scaler injection (deterministic layout).

    Returns:
        Dart source with common LLM API mistakes corrected.
    """
    updated = fix_invalid_alignment_literals(source)
    updated = fix_llm_dart_api_mistakes(updated)
    if include_text_scaler:
        updated = ensure_text_scaler_support(updated)
    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

    delimiter_error = validate_dart_delimiters(updated)
    if delimiter_error is not None:
        logger.warning(
            "Postprocess broke Dart delimiters ({}); keeping pre-postprocess source",
            delimiter_error,
        )
        return source
    return updated


def fix_llm_dart_api_mistakes(source: str) -> str:
    """Rewrite common invalid Flutter API tokens emitted by LLMs.

    Args:
        source: Dart widget or screen source.

    Returns:
        Dart source with gesture/icon fixes applied.
    """
    updated = source
    for wrong, right in _GESTURE_DETECTOR_PARAM_FIXES.items():
        updated = re.sub(rf"\b{re.escape(wrong)}\s*:", f"{right}:", updated)
    for wrong, right in _ICON_GETTER_REPLACEMENTS.items():
        updated = updated.replace(f"Icons.{wrong}", f"Icons.{right}")
    updated = _fix_animated_cross_fade_params(updated)
    updated = _fix_slider_theme_pressed_thumb_radius(updated)
    updated = _fix_slider_component_shape_paint_signatures(updated)
    updated = _fix_on_pressed_on_tap_widgets(updated)
    updated = _fix_on_pressed_on_non_button_widgets(updated)
    updated = _fix_dart_math_min_max_calls(updated)
    updated = _fix_invalid_font_weights(updated)
    updated = _fix_dart_async_timer_usage(updated)
    updated = _strip_invalid_llm_named_parameters(updated)
    updated = strip_llm_viewport_scale_hack(updated)
    updated = strip_llm_responsive_layout_builder(updated)
    updated = fix_misused_text_align_widget(updated)
    updated = fix_misused_transform_origin_alignment(updated)
    updated = fix_malformed_closure_syntax(updated)
    updated = _ensure_material_button_callbacks(updated)
    updated = _ensure_flutter_gestures_import(updated)
    return updated


def fix_misused_text_align_widget(source: str) -> str:
    """Map ``textAlign: Center`` (widget class) to ``TextAlign.center``."""
    return _MISUSED_TEXT_ALIGN_WIDGET_RE.sub(
        lambda match: f"textAlign: TextAlign.{match.group('align').lower()}",
        source,
    )


def fix_misused_transform_origin_alignment(source: str) -> str:
    """Map ``origin: Alignment.center`` to ``alignment: Alignment.center`` on transforms."""
    return _MISUSED_TRANSFORM_ORIGIN_ALIGNMENT_RE.sub(
        r"alignment: Alignment.\1",
        source,
    )


_SCREEN_SCALE_TRANSFORM_RE = re.compile(
    r"Transform\.scale\s*\(\s*scale:\s*(?:screenScale|screenWidth\s*/\s*canvasWidth)\b"
)
_SCREEN_SCALE_DECL_RE = re.compile(
    r"^[ \t]*final\s+double\s+screenScale\s*=.*?;\s*\n?",
    re.MULTILINE,
)
_SCREEN_WIDTH_FOR_SCALE_DECL_RE = re.compile(
    r"^[ \t]*final\s+double\s+screenWidth\s*=\s*MediaQuery\.of\([^)]+\)\.size\.width;\s*\n?",
    re.MULTILINE,
)


def strip_llm_viewport_scale_hack(source: str) -> str:
    """Remove LLM ``screenWidth / canvasWidth`` scale wrappers that blow up wide layouts."""
    updated = source
    while True:
        match = _SCREEN_SCALE_TRANSFORM_RE.search(updated)
        if match is None:
            break
        open_paren = updated.find("(", match.start())
        close_paren = _find_matching_paren(updated, open_paren)
        if close_paren is None:
            break
        inner = updated[open_paren + 1 : close_paren]
        child_match = re.search(r"\bchild:\s*", inner)
        if child_match is None:
            break
        child_start = open_paren + 1 + child_match.end()
        while child_start < len(updated) and updated[child_start].isspace():
            child_start += 1
        child_end = _dart_expression_end(updated, child_start)
        if child_end is None:
            break
        child_expr = updated[child_start:child_end].strip()
        updated = updated[: match.start()] + child_expr + updated[close_paren + 1 :]
    updated = _SCREEN_SCALE_DECL_RE.sub("", updated)
    updated = _SCREEN_WIDTH_FOR_SCALE_DECL_RE.sub("", updated)
    return updated


_RESPONSIVE_LAYOUT_BUILDER_RE = re.compile(r"LayoutBuilder\s*\(\s*builder:\s*\(")
_SCALE_FROM_CONSTRAINTS_RE = re.compile(
    r"constraints\.max(?:Width|Height)\s*/\s*(?:design|canvas)(?:Width|Height)",
    re.IGNORECASE,
)
_UNWRAP_SINGLE_CHILD_PREFIXES = (
    "SingleChildScrollView",
    "GestureDetector",
    "SizedBox",
    "Center",
    "FittedBox",
    "Align",
    "Padding",
)


def unscale_design_expressions(source: str) -> str:
    """Replace ``287.0 * scaleY``-style LLM responsive math with fixed design coordinates."""
    updated = source
    for pattern in (
        r"(\d+(?:\.\d+)?)\s*\*\s*scaleX\b",
        r"(\d+(?:\.\d+)?)\s*\*\s*scaleY\b",
        r"(\d+(?:\.\d+)?)\s*\*\s*scale\b",
    ):
        updated = re.sub(pattern, r"\1", updated)
    updated = re.sub(
        r"width:\s*constraints\.maxWidth\b",
        "width: designWidth",
        updated,
    )
    updated = re.sub(
        r"height:\s*designHeight\s*\*\s*scaleY\b",
        "height: designHeight",
        updated,
    )
    return updated


def _unwrap_single_child_widget(expr: str) -> str:
    """Peel scroll/gesture wrappers until a ``Stack`` or leaf widget remains."""
    current = expr.strip().rstrip(",").rstrip(";")
    for _ in range(24):
        if current.startswith("Stack("):
            return current
        matched_prefix = False
        for prefix in _UNWRAP_SINGLE_CHILD_PREFIXES:
            token = f"{prefix}("
            if not current.startswith(token):
                continue
            matched_prefix = True
            open_paren = len(token) - 1
            close_paren = _find_matching_paren(current, open_paren)
            if close_paren is None:
                return current
            inner = current[open_paren + 1 : close_paren]
            child_match = re.search(r"\bchild:\s*", inner)
            if child_match is None:
                return current
            child_start = open_paren + 1 + child_match.end()
            while child_start < len(current) and current[child_start].isspace():
                child_start += 1
            child_end = _dart_expression_end(current, child_start)
            if child_end is None:
                return current
            current = current[child_start:child_end].strip().rstrip(",").rstrip(";")
            break
        if not matched_prefix:
            break
    return current


def _extract_builder_return_expression(builder_body: str) -> str | None:
    returns = list(re.finditer(r"\breturn\s+", builder_body))
    if not returns:
        return None
    return_start = returns[-1].end()
    while return_start < len(builder_body) and builder_body[return_start].isspace():
        return_start += 1
    expr_end = _dart_expression_end(builder_body, return_start)
    if expr_end is None:
        return None
    return builder_body[return_start:expr_end].strip().rstrip(",").rstrip(";")


def extract_responsive_layout_builder_stack(layout_builder_block: str) -> str | None:
    """Return an unscaled UI ``Stack`` from an LLM ``LayoutBuilder`` scale hack, if present."""
    if "scaleX" not in layout_builder_block and not _SCALE_FROM_CONSTRAINTS_RE.search(
        layout_builder_block
    ):
        return None
    builder_match = re.search(r"builder:\s*\(", layout_builder_block)
    if builder_match is None:
        return None
    params_open = builder_match.end() - 1
    params_close = _find_matching_paren(layout_builder_block, params_open)
    if params_close is None:
        return None
    body_index = params_close + 1
    while body_index < len(layout_builder_block) and layout_builder_block[body_index] in " \t\n\r":
        body_index += 1
    if body_index >= len(layout_builder_block) or layout_builder_block[body_index] != "{":
        return None
    from figma_flutter_agent.generator.llm_dart import _find_matching_brace

    body_close = _find_matching_brace(layout_builder_block, body_index)
    if body_close is None:
        return None
    builder_body = layout_builder_block[body_index + 1 : body_close]
    return_expr = _extract_builder_return_expression(builder_body)
    if return_expr is None:
        return None
    stack_widget = _unwrap_single_child_widget(return_expr)
    if not stack_widget.startswith("Stack("):
        return None
    return unscale_design_expressions(stack_widget)


def strip_llm_responsive_layout_builder(source: str) -> str:
    """Unwrap LLM ``LayoutBuilder`` + ``scaleX``/``scaleY`` layers that duplicate the design canvas."""
    updated = source
    search_from = 0
    while True:
        match = _RESPONSIVE_LAYOUT_BUILDER_RE.search(updated, search_from)
        if match is None:
            break
        open_paren = updated.find("(", match.start())
        close_paren = _find_matching_paren(updated, open_paren)
        if close_paren is None:
            break
        block = updated[match.start() : close_paren + 1]
        stack_widget = extract_responsive_layout_builder_stack(block)
        if stack_widget is None:
            search_from = close_paren + 1
            continue
        updated = updated[: match.start()] + stack_widget + updated[close_paren + 1 :]
        search_from = match.start() + len(stack_widget)
    return updated


def fix_malformed_closure_syntax(source: str) -> str:
    """Rewrite broken empty closures such as ``() {, child:`` emitted by LLMs."""
    return _MALFORMED_EMPTY_CLOSURE_COMMA_RE.sub("() {},", source)


def strip_named_parameter(source: str, param_name: str) -> str:
    """Delete one named argument and its value from Dart source."""
    return _strip_named_parameter(source, param_name)


def _snap_font_weight(value: int) -> int:
    """Map arbitrary Figma weights to Flutter's hundred-step ``FontWeight`` values."""
    snapped = int(round(value / 100.0) * 100)
    return max(100, min(900, snapped))


def _fix_invalid_font_weights(source: str) -> str:
    """Rewrite invalid ``FontWeight.w###`` tokens such as ``w750``."""

    def _replace(match: re.Match[str]) -> str:
        value = int(match.group(1))
        if value in _VALID_FONT_WEIGHTS:
            return match.group(0)
        return f"FontWeight.w{_snap_font_weight(value)}"

    return _FONT_WEIGHT_RE.sub(_replace, source)


def _fix_dart_math_min_max_calls(source: str) -> str:
    """Prefix bare ``min``/``max`` calls and ensure ``dart:math`` is imported."""
    needs_min = _DART_MATH_MIN_RE.search(source) is not None
    needs_max = _DART_MATH_MAX_RE.search(source) is not None
    needs_math_prefix = re.search(r"\bmath\.", source) is not None
    if not needs_min and not needs_max and not needs_math_prefix:
        return source

    updated = source
    if needs_min:
        updated = _DART_MATH_MIN_RE.sub("math.min(", updated)
    if needs_max:
        updated = _DART_MATH_MAX_RE.sub("math.max(", updated)
    return _insert_dart_library_import(updated, "dart:math", alias="math")


def _fix_dart_async_timer_usage(source: str) -> str:
    """Ensure ``dart:async`` is imported when generated code references ``Timer``."""
    if _TIMER_USAGE_RE.search(source) is None:
        return source
    return _insert_dart_library_import(source, "dart:async")


def _strip_invalid_llm_named_parameters(source: str) -> str:
    """Remove hallucinated named parameters from widget constructor calls."""
    updated = source
    for param_name in _INVALID_LLM_NAMED_PARAMS:
        updated = _strip_named_parameter(updated, param_name)
    return updated


def _strip_named_parameter(source: str, param_name: str) -> str:
    """Delete one named argument and its value from Dart source."""
    token = f"{param_name}:"
    while True:
        index = source.find(token)
        if index == -1:
            break
        start = index
        while start > 0 and source[start - 1].isspace():
            start -= 1
        if start > 0 and source[start - 1] == ",":
            start -= 1

        value_start = index + len(token)
        value_end = _dart_expression_end(source, value_start)
        if value_end is None:
            break
        end = value_end
        while end < len(source) and source[end].isspace():
            end += 1
        if end < len(source) and source[end] == ",":
            end += 1
        source = source[:start] + source[end:]
    return source


def _extend_trailing_function_body(source: str, value_end: int) -> int:
    """Include a trailing ``{ ... }`` block after ``()`` callback expressions."""
    tail = value_end
    while tail < len(source) and source[tail].isspace():
        tail += 1
    if tail < len(source) and source[tail] == "{":
        close_index = _find_matching_bracket(source, tail, "{", "}")
        if close_index is not None:
            return close_index + 1
    return value_end


def _extract_named_argument_value(block: str, param_name: str) -> str | None:
    """Return the raw value for ``param_name:`` inside one widget constructor block."""
    token = f"{param_name}:"
    index = block.find(token)
    if index == -1:
        return None
    value_start = index + len(token)
    value_end = _dart_expression_end(block, value_start)
    if value_end is None:
        return None
    return block[value_start:value_end].strip()


def _dart_expression_end(source: str, start: int) -> int | None:
    """Return the index after a Dart expression beginning at ``start``."""
    index = start
    while index < len(source) and source[index].isspace():
        index += 1
    if index >= len(source):
        return index

    if source.startswith("const ", index):
        index += len("const ")
        while index < len(source) and source[index].isspace():
            index += 1

    char = source[index]
    if char == "(":
        close_index = _find_matching_paren(source, index)
        if close_index is None:
            return None
        value_end = close_index + 1
        return _extend_trailing_function_body(source, value_end)
    if char == "[":
        close_index = _find_matching_bracket(source, index, "[", "]")
        return None if close_index is None else close_index + 1
    if char == "{":
        close_index = _find_matching_bracket(source, index, "{", "}")
        return None if close_index is None else close_index + 1
    if char in {"'", '"'}:
        return _dart_string_literal_end(source, index)

    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    for position in range(index, len(source)):
        char_at = source[position]
        if in_string:
            if escape:
                escape = False
                continue
            if char_at == "\\":
                escape = True
                continue
            if char_at == string_quote:
                in_string = False
            continue

        if char_at in {"'", '"'}:
            in_string = True
            string_quote = char_at
            continue
        if char_at == "(":
            depth += 1
            continue
        if char_at == ")":
            if depth == 0:
                return position
            depth -= 1
            continue
        if char_at == "," and depth == 0:
            return position
    return len(source)


def _dart_string_literal_end(source: str, start: int) -> int | None:
    if start >= len(source) or source[start] not in {"'", '"'}:
        return None
    quote = source[start]
    escape = False
    for index in range(start + 1, len(source)):
        char = source[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == quote:
            return index + 1
    return None


def _insert_dart_library_import(
    source: str,
    library: str,
    *,
    alias: str | None = None,
) -> str:
    """Insert a ``dart:*`` import after ``material.dart`` when missing."""
    if re.search(rf"""import\s+['"]{re.escape(library)}['"]""", source):
        return source

    import_line = f"import '{library}' as {alias};" if alias else f"import '{library}';"
    material_import = "import 'package:flutter/material.dart';"
    if material_import in source:
        return source.replace(
            material_import,
            f"{material_import}\n\n{import_line}",
            1,
        )

    match = re.search(r"^import .+;\s*$", source, re.MULTILINE)
    if match is None:
        return f"{import_line}\n\n{source}"
    insert_at = match.end()
    return source[:insert_at] + f"\n{import_line}" + source[insert_at:]


def _insert_dart_math_import(source: str) -> str:
    """Insert ``import 'dart:math' as math;`` when missing."""
    return _insert_dart_library_import(source, "dart:math", alias="math")


def _fix_animated_cross_fade_params(source: str) -> str:
    """Rewrite ``first``/``second`` to ``firstChild``/``secondChild`` on AnimatedCrossFade."""
    parts: list[str] = []
    index = 0
    token = "AnimatedCrossFade"
    while True:
        start = source.find(token, index)
        if start == -1:
            parts.append(source[index:])
            break
        parts.append(source[index:start])
        paren_start = source.find("(", start)
        if paren_start == -1:
            parts.append(source[start:])
            break
        paren_end = _find_matching_paren(source, paren_start)
        if paren_end is None:
            parts.append(source[start:])
            break
        block = source[start : paren_end + 1]
        block = re.sub(r"\bfirst\s*:", "firstChild:", block)
        block = re.sub(r"\bsecond\s*:", "secondChild:", block)
        parts.append(block)
        index = paren_end + 1
    return "".join(parts)


def _fix_slider_theme_pressed_thumb_radius(source: str) -> str:
    """Move ``pressedThumbRadius`` from ``SliderThemeData`` onto ``RoundSliderThumbShape``."""
    if "SliderThemeData" not in source or "pressedThumbRadius" not in source:
        return source

    parts: list[str] = []
    index = 0
    token = "SliderThemeData"
    while True:
        start = source.find(token, index)
        if start == -1:
            parts.append(source[index:])
            break
        parts.append(source[index:start])
        paren_start = source.find("(", start)
        if paren_start == -1:
            parts.append(source[start:])
            break
        paren_end = _find_matching_paren(source, paren_start)
        if paren_end is None:
            parts.append(source[start:])
            break
        block = source[start : paren_end + 1]
        if "thumbShape:" not in block:
            block = re.sub(
                r"\bpressedThumbRadius\s*:\s*([^,\n)]+)\s*,?",
                r"thumbShape: RoundSliderThumbShape(pressedThumbRadius: \1),",
                block,
            )
        else:
            block = re.sub(r"\bpressedThumbRadius\s*:\s*[^,\n)]+\s*,?\s*", "", block)
        parts.append(block)
        index = paren_end + 1
    return "".join(parts)


def _fix_slider_component_shape_paint_signatures(source: str) -> str:
    """Fix invalid ``SliderComponentShape.paint`` signatures emitted by LLMs."""
    if not any(
        token in source
        for token in (
            "SliderComponentShape",
            "RoundSliderThumbShape",
            "SliderThemeData",
            "ThumbShape",
        )
    ):
        return source

    updated = source.replace("LabelPainter", "TextPainter")
    if "isHorizontal" not in updated:
        return updated
    return re.sub(r"\bisHorizontal\b", "isDiscrete", updated)


def _ensure_flutter_gestures_import(source: str) -> str:
    """Insert ``flutter/gestures.dart`` when ``TapGestureRecognizer`` is referenced."""
    if _TAP_GESTURE_RECOGNIZER_RE.search(source) is None:
        return source
    if re.search(r"""import\s+['"]package:flutter/gestures\.dart['"]""", source):
        return source
    material_import = "import 'package:flutter/material.dart';"
    gestures_import = "import 'package:flutter/gestures.dart';"
    if material_import in source:
        return source.replace(material_import, f"{material_import}\n{gestures_import}", 1)
    return f"{gestures_import}\n\n{source}"


def _ensure_material_button_callbacks(source: str) -> str:
    """Add no-op ``onPressed`` callbacks required by Material button widgets."""
    updated = source
    for widget_name in _BUTTON_WIDGETS:
        updated = _ensure_widget_has_on_pressed(updated, widget_name)
    return updated


def _ensure_widget_has_on_pressed(source: str, widget_name: str) -> str:
    """Ensure ``widget_name(...)`` includes ``onPressed`` when missing."""
    parts: list[str] = []
    index = 0
    token = widget_name
    while True:
        start = source.find(token, index)
        if start == -1:
            parts.append(source[index:])
            break
        parts.append(source[index:start])
        paren_start = source.find("(", start)
        if paren_start == -1:
            parts.append(source[start:])
            break
        paren_end = _find_matching_paren(source, paren_start)
        if paren_end is None:
            parts.append(source[start:])
            break
        block = source[start : paren_end + 1]
        if re.search(r"\bonPressed\s*:", block) or re.search(r"\bonTap\s*:", block):
            parts.append(block)
        else:
            inner = block[len(widget_name) + 1 : -1].strip()
            if not inner:
                patched = f"{widget_name}(onPressed: () {{}})"
            else:
                patched = f"{widget_name}(onPressed: () {{}}, {inner})"
            parts.append(patched)
        index = paren_end + 1
    return "".join(parts)


def _fix_on_pressed_on_tap_widgets(source: str) -> str:
    """Rewrite ``onPressed`` to ``onTap`` on widgets that only support tap callbacks."""
    updated = source
    for widget_name in ("GestureDetector", "InkWell", "InkResponse"):
        updated = _replace_direct_named_param_in_widget_ctor(
            updated, widget_name, "onPressed", "onTap"
        )
    return updated


def _replace_direct_named_param_in_widget_ctor(
    source: str,
    widget_name: str,
    old_param: str,
    new_param: str,
) -> str:
    """Replace a named parameter only on the direct widget call, not nested children."""
    parts: list[str] = []
    index = 0
    token = widget_name
    while True:
        start = source.find(token, index)
        if start == -1:
            parts.append(source[index:])
            break
        parts.append(source[index:start])
        paren_start = source.find("(", start)
        if paren_start == -1:
            parts.append(source[start:])
            break
        paren_end = _find_matching_paren(source, paren_start)
        if paren_end is None:
            parts.append(source[start:])
            break
        inner = source[paren_start + 1 : paren_end]
        updated_inner = _replace_top_level_named_param(inner, old_param, new_param)
        parts.append(f"{widget_name}({updated_inner})")
        index = paren_end + 1
    return "".join(parts)


def _replace_top_level_named_param(inner: str, old_param: str, new_param: str) -> str:
    token = f"{old_param}:"
    index = 0
    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    while index < len(inner):
        char = inner[index]
        if in_string:
            if escape:
                escape = False
                index += 1
                continue
            if char == "\\":
                escape = True
                index += 1
                continue
            if char == string_quote:
                in_string = False
            index += 1
            continue
        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            index += 1
            continue
        if char in "([{":
            depth += 1
            index += 1
            continue
        if char in ")]}":
            depth = max(0, depth - 1)
            index += 1
            continue
        if depth == 0 and inner.startswith(token, index):
            return inner[:index] + inner[index:].replace(token, f"{new_param}:", 1)
        index += 1
    return inner


def _replace_named_param_in_widget_ctor(
    source: str,
    widget_name: str,
    old_param: str,
    new_param: str,
) -> str:
    """Replace a named parameter inside one widget constructor call."""
    parts: list[str] = []
    index = 0
    token = widget_name
    while True:
        start = source.find(token, index)
        if start == -1:
            parts.append(source[index:])
            break
        parts.append(source[index:start])
        paren_start = source.find("(", start)
        if paren_start == -1:
            parts.append(source[start:])
            break
        paren_end = _find_matching_paren(source, paren_start)
        if paren_end is None:
            parts.append(source[start:])
            break
        block = source[start : paren_end + 1]
        block = re.sub(rf"\b{re.escape(old_param)}\s*:", f"{new_param}:", block)
        parts.append(block)
        index = paren_end + 1
    return "".join(parts)


_ON_PRESSED_NON_BUTTON_WIDGETS = (
    "Material",
    "Container",
    "SizedBox",
    "Padding",
    "Align",
    "Center",
    "ClipOval",
    "DecoratedBox",
    "CircleAvatar",
    "Icon",
)


def _fix_on_pressed_on_non_button_widgets(source: str) -> str:
    """Wrap non-button widgets that incorrectly declare ``onPressed`` in ``GestureDetector``."""
    updated = source
    for widget_name in _ON_PRESSED_NON_BUTTON_WIDGETS:
        updated = _wrap_widget_on_pressed_with_gesture_detector(updated, widget_name)
    return updated


def _wrap_widget_on_pressed_with_gesture_detector(source: str, widget_name: str) -> str:
    """Move ``onPressed`` from ``widget_name(...)`` onto a wrapping ``GestureDetector``."""
    parts: list[str] = []
    index = 0
    opener = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(widget_name)}\(")
    while True:
        match = opener.search(source, index)
        if match is None:
            parts.append(source[index:])
            break
        start = match.start()
        parts.append(source[index:start])
        paren_start = match.end() - 1
        if paren_start == -1:
            parts.append(source[start:])
            break
        paren_end = _find_matching_paren(source, paren_start)
        if paren_end is None:
            parts.append(source[start:])
            break
        block = source[start : paren_end + 1]
        if "onPressed:" not in block:
            parts.append(block)
            index = paren_end + 1
            continue
        callback = _extract_named_argument_value(block, "onPressed")
        if callback is None:
            parts.append(block)
            index = paren_end + 1
            continue
        cleaned = _strip_named_parameter(block, "onPressed")
        parts.append(f"GestureDetector(onTap: {callback}, child: {cleaned})")
        index = paren_end + 1
    return "".join(parts)


def fix_invalid_alignment_literals(source: str) -> str:
    """Rewrite invalid ``Alignment.*`` getters LLMs often emit.

    LLMs confuse ``Alignment``, ``AlignmentDirectional``, ``CrossAxisAlignment``,
    and ``MainAxisAlignment``. Replacements depend on the surrounding parameter name.

    Args:
        source: Dart source that may reference invalid ``Alignment`` getters.

    Returns:
        Dart source with corrected alignment enum references.
    """
    updated = _MISUSED_ALIGNMENT_PARAM_RE.sub(_replace_misused_alignment_param, source)

    def _replace_bare(match: re.Match[str]) -> str:
        member = match.group(1)
        return _ALIGN_WIDGET_REPLACEMENTS.get(member, match.group(0))

    return _INVALID_ALIGNMENT_RE.sub(_replace_bare, updated)


def _replace_misused_alignment_param(match: re.Match[str]) -> str:
    param = match.group("param")
    member = match.group("member")
    if param == "alignment":
        replacement = _ALIGN_WIDGET_REPLACEMENTS.get(member)
    elif param == "crossAxisAlignment":
        replacement = _CROSS_AXIS_REPLACEMENTS.get(member)
    else:
        replacement = _MAIN_AXIS_REPLACEMENTS.get(member)
    if replacement is None:
        return match.group(0)
    return f"{param}: {replacement}"


def ensure_text_scaler_support(source: str) -> str:
    """Ensure LLM-generated Dart declares ``MediaQuery.textScalerOf``.

    Deterministic layout injects ``textScaler`` in ``build``; LLM output may omit it
    or place ``Text`` in helper methods and builder callbacks. This function wires
    ``textScaler: MediaQuery.textScalerOf(<context>)`` on each ``Text`` widget when
    missing so codegen validation passes and text respects user scaling.

    Args:
        source: Raw or templated Dart widget or screen source.

    Returns:
        Dart source with text-scaler support when it was missing.
    """
    updated = _ensure_helper_methods_have_build_context(source)
    updated = _fix_out_of_scope_text_scaler_references(updated)
    if (
        _TEXT_SCALER_DECL_RE.search(updated)
        and not _text_widgets_missing_scaler(updated)
        and "textScaler: textScaler" not in updated
    ):
        updated = _remove_unused_text_scaler_declarations(updated)
        return updated
    updated = _attach_text_scaler_to_text_widgets(updated)
    updated = _strip_const_around_runtime_text_scaler(updated)
    if _TEXT_DISPLAY_WIDGET_RE.search(updated) and _text_widgets_missing_scaler(updated):
        updated = _inject_build_text_scaler_declaration(updated)
        updated = _attach_text_scaler_to_text_widgets(updated)
        updated = _strip_const_around_runtime_text_scaler(updated)
    updated = _fix_out_of_scope_text_scaler_references(updated)
    updated = _ensure_helper_methods_have_build_context(updated)
    if "textScaler: textScaler" not in updated:
        updated = _remove_unused_text_scaler_declarations(updated)
    return updated


_TEXT_SCALER_DECL_LINE_RE = re.compile(
    r"^[ \t]*(?:final|var)\s+textScaler\s*=\s*MediaQuery\.textScalerOf\([^)]+\);\s*\n?",
    re.MULTILINE,
)


def _remove_unused_text_scaler_declarations(source: str) -> str:
    """Drop orphan ``textScaler`` locals when every ``Text`` uses inline MediaQuery."""
    if "textScaler: textScaler" in source:
        return source
    if not _TEXT_SCALER_DECL_LINE_RE.search(source):
        return source
    stripped = _TEXT_SCALER_DECL_LINE_RE.sub("", source)
    if re.search(r"(?<![.\w])textScaler\b(?!\s*:)", stripped):
        return source
    return stripped


def _text_scaler_local_in_scope(source: str, index: int) -> bool:
    """Return whether ``textScaler`` is declared in the same function body as ``index``."""
    brace_open = _find_enclosing_brace_open(source, index)
    if brace_open is None:
        return False
    brace_close = _find_matching_bracket(source, brace_open, "{", "}")
    if brace_close is None:
        return False
    body = source[brace_open : brace_close + 1]
    return re.search(
        r"\b(?:final|var)\s+textScaler\s*=\s*MediaQuery\.textScalerOf\(",
        body,
    ) is not None


def _fix_out_of_scope_text_scaler_references(source: str) -> str:
    """Replace ``textScaler: textScaler`` with inline MediaQuery when local is out of scope."""
    parts: list[str] = []
    index = 0
    for match in _TEXT_WIDGET_RE.finditer(source):
        call_start = match.end() - 1
        call_end = _find_matching_paren(source, call_start)
        if call_end is None:
            continue
        call = source[call_start : call_end + 1]
        if "textScaler: textScaler" not in call:
            continue
        if _text_scaler_local_in_scope(source, match.start()):
            continue
        context_name = _context_name_for_position(source, match.start())
        if context_name is None:
            continue
        fixed_call = call.replace(
            "textScaler: textScaler",
            f"textScaler: MediaQuery.textScalerOf({context_name})",
        )
        parts.append(source[index:call_start])
        parts.append(fixed_call)
        index = call_end + 1
    if not parts:
        return source
    parts.append(source[index:])
    return "".join(parts)


def _enclosing_method_body(source: str, index: int) -> str | None:
    """Return the body of the innermost method or builder block containing ``index``."""
    brace_open = _find_enclosing_brace_open(source, index)
    if brace_open is None:
        return None
    brace_close = _find_matching_bracket(source, brace_open, "{", "}")
    if brace_close is None:
        return None
    return source[brace_open : brace_close + 1]


def _inject_build_text_scaler_declaration(source: str) -> str:
    """Declare ``textScaler`` in ``build`` when inline patching did not run."""
    match = _BUILD_METHOD_RE.search(source)
    if match is None:
        return source
    context_name = match.group("context")
    insert_at = match.end()
    declaration = f"\n    final textScaler = MediaQuery.textScalerOf({context_name});"
    return source[:insert_at] + declaration + source[insert_at:]


def _text_widgets_missing_scaler(source: str) -> bool:
    for match in _TEXT_WIDGET_RE.finditer(source):
        call_start = match.end() - 1
        call_end = _find_matching_paren(source, call_start)
        if call_end is None:
            continue
        call = source[call_start : call_end + 1]
        if "textScaler:" not in call:
            return True
    return False


def _attach_text_scaler_to_text_widgets(source: str) -> str:
    parts: list[str] = []
    index = 0
    for match in _TEXT_WIDGET_RE.finditer(source):
        text_start = match.start()
        prefix = source[index:text_start]
        prefix = _CONST_BEFORE_TEXT_RE.sub("", prefix)
        parts.append(prefix)

        call_start = match.end() - 1
        call_end = _find_matching_paren(source, call_start)
        if call_end is None:
            parts.append(source[text_start:])
            return "".join(parts)

        call = source[call_start : call_end + 1]
        if "textScaler:" in call:
            parts.append(source[text_start : call_end + 1])
        else:
            context_name = _context_name_for_position(source, text_start)
            if context_name is None:
                parts.append(source[text_start : call_end + 1])
            else:
                parts.append(_patch_text_call(call, context_name))
        index = call_end + 1

    parts.append(source[index:])
    return "".join(parts)


_RUNTIME_TEXT_SCALER = "textScaler: MediaQuery.textScalerOf("


def _strip_const_around_runtime_text_scaler(source: str) -> str:
    if _RUNTIME_TEXT_SCALER not in source:
        return source

    updated = source
    while True:
        stripped = _strip_one_const_around_runtime_text_scaler(updated)
        if stripped == updated:
            return updated
        updated = stripped


def _strip_one_const_around_runtime_text_scaler(source: str) -> str:
    for match in reversed(list(re.finditer(r"\bconst\s+", source))):
        expr_start = match.end()
        if expr_start >= len(source):
            continue

        expr_end = _const_expression_end(source, expr_start)
        if expr_end is None:
            continue

        if _RUNTIME_TEXT_SCALER in source[expr_start:expr_end]:
            return source[: match.start()] + source[match.end() :]
    return source


def _const_expression_end(source: str, start: int) -> int | None:
    char = source[start]
    if char == "[":
        close_index = _find_matching_bracket(source, start, "[", "]")
        return None if close_index is None else close_index + 1
    if char == "{":
        close_index = _find_matching_bracket(source, start, "{", "}")
        return None if close_index is None else close_index + 1
    if char == "(":
        close_index = _find_matching_paren(source, start)
        return None if close_index is None else close_index + 1

    widget_match = re.match(r"\w+\s*\(", source[start:])
    if widget_match is None:
        return None
    paren_start = start + widget_match.end() - 1
    close_index = _find_matching_paren(source, paren_start)
    return None if close_index is None else close_index + 1


def _find_matching_bracket(
    source: str,
    open_index: int,
    open_char: str,
    close_char: str,
) -> int | None:
    if open_index >= len(source) or source[open_index] != open_char:
        return None

    depth = 0
    in_string = False
    string_quote = ""
    escape = False

    for index in range(open_index, len(source)):
        char = source[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == string_quote:
                in_string = False
            continue

        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            continue
        if char == open_char:
            depth += 1
            continue
        if char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return None


def _build_context_param_before_brace(source: str, brace_index: int) -> str | None:
    """Return the BuildContext parameter for the block opened at ``brace_index``."""
    prefix = source[:brace_index].rstrip()
    if not prefix or prefix[-1] != ")":
        return None
    close_paren = len(prefix) - 1
    open_paren = _find_matching_paren_backwards(prefix, close_paren)
    if open_paren is None:
        return None
    param_region = prefix[open_paren + 1 : close_paren]
    return _build_context_name_from_param_list(param_region)


def _build_context_name_from_param_list(param_region: str) -> str | None:
    """Resolve a BuildContext parameter from a Dart parameter list."""
    match = _BUILD_CONTEXT_PARAM_RE.search(param_region)
    if match is not None:
        return match.group("context")

    trimmed = param_region.strip()
    if not trimmed:
        return None

    first = trimmed.split(",", 1)[0].strip()
    typed = re.match(r"^BuildContext\s+(\w+)$", first)
    if typed is not None:
        return typed.group(1)

    if re.match(r"^\w+$", first) is not None:
        return first
    return None


def _is_class_method_body(source: str, body_open: int) -> bool:
    """Return whether ``body_open`` starts a class-level method body."""
    window = source[max(0, body_open - 320) : body_open]
    return bool(
        re.search(
            r"(?:^|\n)[ \t]*(?:@\w+(?:\([^\)]*\))?\s*\n[ \t]*)?"
            r"(?:Widget|void|bool|int|String|double|Future|List|Map|\w+)"
            r"\s+\w+\s*\([^)]*\)\s*(?:async\s*)?\{\s*$",
            window,
            re.MULTILINE,
        )
    )


def _build_method_context_name(source: str) -> str | None:
    """Return the BuildContext parameter name from ``build`` when present."""
    match = _BUILD_METHOD_RE.search(source)
    return match.group("context") if match else None


def _method_params_include_build_context(params: str) -> bool:
    return _BUILD_CONTEXT_PARAM_RE.search(params) is not None


def _prefix_helper_calls_with_context(
    source: str,
    method_name: str,
    context_name: str,
) -> str:
    """Pass ``build``'s context into helper invocations that omit it."""

    def _replace_call(match: re.Match[str]) -> str:
        tail = source[match.end() :]
        if re.match(r"\s*\{", tail):
            return match.group(0)
        args = match.group(1).strip()
        if not args:
            return f"{method_name}({context_name})"
        first_arg = args.split(",", 1)[0].strip()
        if first_arg == context_name:
            return match.group(0)
        return f"{method_name}({context_name}, {args})"

    return re.sub(
        rf"\b{re.escape(method_name)}\s*\(([^)]*)\)",
        _replace_call,
        source,
    )


def _ensure_helper_methods_have_build_context(source: str) -> str:
    """Add ``BuildContext`` to helpers that reference ``context`` out of scope."""
    build_context_name = _build_method_context_name(source)
    updated = source
    for match in list(_HELPER_METHOD_SIGNATURE_RE.finditer(updated)):
        params = match.group("params").strip()
        if _method_params_include_build_context(params):
            continue

        body_open = match.end() - 1
        body_close = _find_matching_bracket(updated, body_open, "{", "}")
        if body_close is None:
            continue
        body = updated[body_open : body_close + 1]
        needs_context = _CONTEXT_REFERENCE_RE.search(body) is not None
        if not needs_context and _TEXT_DISPLAY_WIDGET_RE.search(body):
            needs_context = _text_widgets_missing_scaler(body)
        if not needs_context:
            continue

        method_name = match.group("name")
        new_params = "BuildContext context" if not params else f"BuildContext context, {params}"
        signature = match.group(0)
        new_signature = signature.replace(
            f"{method_name}({match.group('params')})",
            f"{method_name}({new_params})",
            1,
        )
        updated = updated.replace(signature, new_signature, 1)
        if build_context_name is not None:
            updated = _prefix_helper_calls_with_context(
                updated,
                method_name,
                build_context_name,
            )
    return updated


def _find_matching_paren_backwards(source: str, close_index: int) -> int | None:
    if close_index >= len(source) or source[close_index] != ")":
        return None

    depth = 0
    in_string = False
    string_quote = ""
    escape = False

    for index in range(close_index, -1, -1):
        char = source[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == string_quote:
                in_string = False
            continue

        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            continue
        if char == ")":
            depth += 1
            continue
        if char == "(":
            depth -= 1
            if depth == 0:
                return index
    return None


def _context_name_for_position(source: str, index: int) -> str | None:
    """Return the nearest in-scope BuildContext parameter name for ``index``."""
    search_end = index
    while True:
        body_open = _find_enclosing_brace_open(source, search_end)
        if body_open is None:
            return None
        context_name = _build_context_param_before_brace(source, body_open)
        if context_name is not None:
            return context_name
        if _is_class_method_body(source, body_open):
            return None
        if body_open == 0:
            return None
        search_end = body_open - 1


def _patch_text_call(call: str, context_name: str) -> str:
    return _patch_text_call_with_scaler(call, f"MediaQuery.textScalerOf({context_name})")


def _patch_text_call_with_scaler(call: str, scaler_expr: str) -> str:
    scaler = f"textScaler: {scaler_expr}"
    inner = call[1:-1].rstrip()
    if not inner:
        return f"Text({scaler})"
    if inner.endswith(","):
        return f"Text({inner} {scaler})"
    return f"Text({inner}, {scaler})"


def _find_enclosing_brace_open(source: str, index: int) -> int | None:
    depth = 0
    for position in range(index - 1, -1, -1):
        char = source[position]
        if char == "}":
            depth += 1
            continue
        if char != "{":
            continue
        if depth == 0:
            return position
        depth -= 1
    return None


def _find_matching_paren(source: str, open_index: int) -> int | None:
    if open_index >= len(source) or source[open_index] != "(":
        return None

    depth = 0
    in_string = False
    string_quote = ""
    escape = False

    for index in range(open_index, len(source)):
        char = source[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == string_quote:
                in_string = False
            continue

        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None
