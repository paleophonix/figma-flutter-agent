"""UTF-8 I/O and AST sidecar dispatch for generated Dart."""

from __future__ import annotations

import re
from pathlib import Path

from figma_flutter_agent.generator.dart_delimiters import (
    find_matching_bracket,
    find_matching_paren,
)
from figma_flutter_agent.tools.ast_sidecar import (
    AstRule,
    apply_ast_rules,
    apply_codegen_ast_rules,
    ensure_named_widgets_on_pressed,
    wrap_widget_on_pressed,
)

_UTF8_ENCODING = "utf-8"

TEXT_DISPLAY_WIDGET_RE = re.compile(
    r"(?<!TextStyle)(?<!TextSpan)\b(?:Text(?:\.rich)?|SelectableText|EditableText|RichText)\s*\("
)
_ORPHAN_TEXT_SCALER_REF_RE = re.compile(r"\btextScaler:\s*textScaler\b")
_TEXT_SCALER_DECL_RE = re.compile(
    r"(?:final|var)\s+textScaler\s*=\s*MediaQuery\.textScalerOf\("
)
_RUNTIME_TEXT_SCALER_MARKER = "textScaler: MediaQuery.textScalerOf("
_CONST_KEYWORD_RE = re.compile(r"\bconst\s+")


def _run_rules(
    source: str,
    rules: tuple[AstRule, ...],
    *,
    include_text_scaler: bool = False,
) -> str:
    return apply_ast_rules(
        source,
        rules,
        include_text_scaler=include_text_scaler,
    ).source


def read_dart_source(path: Path) -> str:
    return path.read_text(encoding=_UTF8_ENCODING)


def write_dart_source(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding=_UTF8_ENCODING)


def process_generated_dart_source(
    source: str,
    *,
    include_text_scaler: bool = True,
    use_ast_sidecar: bool = True,
) -> str:
    if not use_ast_sidecar:
        updated = source
    else:
        updated = apply_codegen_ast_rules(
            source,
            include_text_scaler=include_text_scaler,
        ).source
    if include_text_scaler:
        updated = strip_const_runtime_text_scaler(updated)
    from figma_flutter_agent.generator.dart_file_parts import relocate_directives_to_header

    return relocate_directives_to_header(updated)


def process_generated_dart_file(
    path: Path,
    *,
    include_text_scaler: bool = True,
    use_ast_sidecar: bool = True,
) -> str:
    processed = process_generated_dart_source(
        read_dart_source(path),
        include_text_scaler=include_text_scaler,
        use_ast_sidecar=use_ast_sidecar,
    )
    write_dart_source(path, processed)
    return processed


def fix_text_style_height_as_ratio(source: str) -> str:
    """Rewrite pixel-like ``TextStyle.height`` values to unitless line-height ratios."""
    from figma_flutter_agent.parser.numeric_rounding import format_micro_style_literal
    from figma_flutter_agent.parser.text_line_height import flutter_text_style_height_ratio

    parts: list[str] = []
    last = 0
    for match in re.finditer(r"\bheight:\s*([\d.]+)", source):
        parts.append(source[last : match.start()])
        height_val = float(match.group(1))
        window = source[max(0, match.start() - 600) : match.start()]
        font_matches = list(re.finditer(r"fontSize:\s*([\d.]+)", window))
        if not font_matches:
            parts.append(match.group(0))
        else:
            font_size = float(font_matches[-1].group(1))
            ratio = flutter_text_style_height_ratio(height_val, font_size=font_size)
            if ratio is None or ratio == height_val:
                parts.append(match.group(0))
            else:
                parts.append(f"height: {format_micro_style_literal(ratio)}")
        last = match.end()
    parts.append(source[last:])
    return "".join(parts)


def postprocess_generated_dart(source: str, *, include_text_scaler: bool = True) -> str:
    processed = process_generated_dart_source(source, include_text_scaler=include_text_scaler)
    processed = fix_text_style_height_as_ratio(processed)
    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters
    from loguru import logger

    delimiter_error = validate_dart_delimiters(processed)
    if delimiter_error is not None:
        logger.warning(
            "Postprocess broke Dart delimiters ({}); keeping pre-postprocess source",
            delimiter_error,
        )
        return source
    return processed


def apply_codegen_dart_fixes(
    source: str,
    *,
    include_text_scaler: bool = True,
    layout_via_ast: bool = False,
) -> str:
    del layout_via_ast
    return apply_codegen_ast_rules(
        source,
        include_text_scaler=include_text_scaler,
    ).source


def _wrap_widget_on_pressed_with_gesture_detector(source: str, widget_name: str) -> str:
    return wrap_widget_on_pressed(source, widget_name)


def discover_widgets_requiring_on_pressed(sources: dict[str, str]) -> tuple[str, ...]:
    names: list[str] = []
    required = re.compile(
        r"required\s+(?:this\.)?onPressed\b|required\s+VoidCallback\s+onPressed\b"
    )
    widget_class = re.compile(
        r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
    )
    for path, content in sources.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/") or not normalized.endswith(".dart"):
            continue
        if required.search(content) is None:
            continue
        match = widget_class.search(content)
        if match is not None:
            names.append(match.group("name"))
    return tuple(dict.fromkeys(names))


def ensure_required_on_pressed_callbacks(
    source: str,
    *,
    widget_names: tuple[str, ...],
) -> str:
    return ensure_named_widgets_on_pressed(source, widget_names)


def normalize_llm_dart_string_escapes(source: str) -> str:
    return _run_rules(source, ("normalize_string_literals",))


def strip_bare_unicode_escapes_outside_literals(source: str) -> str:
    return _run_rules(source, ("strip_bare_unicode_escapes",))


def strip_invalid_dart_imports(source: str) -> str:
    return _run_rules(source, ("sanitize_imports",))


def strip_embedded_auto_generated_markers(source: str) -> str:
    return _run_rules(source, ("sanitize_imports",))


def ensure_base_screen_imports(source: str) -> str:
    return _run_rules(source, ("sanitize_imports",))


def _ensure_flutter_gestures_import(source: str) -> str:
    return ensure_base_screen_imports(source)


def ensure_app_colors_import(source: str, *, package_name: str = "demo_app") -> str:
    del package_name
    return _run_rules(source, ("sanitize_imports",))


def fix_llm_dart_api_mistakes(
    source: str,
    *,
    apply_layout_strips: bool = False,
    apply_llm_widget_repairs: bool = True,
) -> str:
    del apply_layout_strips, apply_llm_widget_repairs
    return fix_text_style_height_as_ratio(_run_rules(source, ("fix_llm_api_mistakes",)))


def fix_invalid_alignment_literals(source: str) -> str:
    return _run_rules(source, ("fix_alignment_literals",))


def fix_misused_text_align_widget(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def fix_misused_transform_origin_alignment(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def ensure_text_scaler_support(source: str) -> str:
    return apply_ast_rules(source, (), include_text_scaler=True).source


def inline_orphan_text_scaler_refs(source: str, *, context: str = "context") -> str:
    """Fallback when AST cannot fix layout-spliced ``textScaler: textScaler`` references."""
    if not _ORPHAN_TEXT_SCALER_REF_RE.search(source):
        return source
    if _TEXT_SCALER_DECL_RE.search(source):
        return source
    return _ORPHAN_TEXT_SCALER_REF_RE.sub(
        f"textScaler: MediaQuery.textScalerOf({context})",
        source,
    )


def ensure_bordered_box_decoration_fill(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def ensure_outlined_button_opaque_fill(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def wrap_bare_inkwell_with_material(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def strip_design_canvas_gesture_matryoshka(source: str) -> str:
    return _run_rules(source, ("strip_design_canvas_gesture_matryoshka",))


def strip_llm_viewport_scale_hack(source: str) -> str:
    return _run_rules(source, ("strip_viewport_scale_transform",))


def strip_llm_responsive_layout_builder(source: str) -> str:
    return _run_rules(source, ("unwrap_scale_layout_builder",))


def unscale_design_expressions(source: str) -> str:
    from figma_flutter_agent.generator.dart_unscale import unscale_design_expressions as _unscale

    return _unscale(source)


def strip_named_parameter(source: str, param_name: str) -> str:
    from figma_flutter_agent.generator.dart_postprocess_params import strip_named_parameter as _strip

    return _strip(source, param_name)


def fix_malformed_closure_syntax(source: str) -> str:
    return _run_rules(source, ("fix_llm_api_mistakes",))


def fix_empty_text_before_text_scaler(source: str) -> str:
    return re.sub(
        r"\bText\s*\(\s*,\s*textScaler:",
        "Text('', textScaler:",
        source,
    )


def ensure_text_style_leading_distribution(source: str) -> str:
    return re.sub(
        r"(TextStyle\([^)]*height:\s*[^,)]+)",
        r"\1, leadingDistribution: TextLeadingDistribution.proportional",
        source,
        count=1,
    )


def fix_misplaced_text_style_parameters(source: str) -> str:
    return source


def _const_expression_end(source: str, start: int) -> int | None:
    if start >= len(source):
        return None
    char = source[start]
    if char == "[":
        close = find_matching_bracket(source, start, "[", "]")
        return None if close is None else close + 1
    if char == "{":
        close = find_matching_bracket(source, start, "{", "}")
        return None if close is None else close + 1
    if char == "(":
        close = find_matching_paren(source, start)
        return None if close is None else close + 1
    widget_match = re.match(r"\w+\s*\(", source[start:])
    if widget_match is None:
        return None
    paren_start = start + widget_match.end() - 1
    close = find_matching_paren(source, paren_start)
    return None if close is None else close + 1


def _strip_one_const_around_runtime_text_scaler(source: str) -> str:
    for match in reversed(list(_CONST_KEYWORD_RE.finditer(source))):
        expr_start = match.end()
        expr_end = _const_expression_end(source, expr_start)
        if expr_end is None:
            continue
        if _RUNTIME_TEXT_SCALER_MARKER in source[expr_start:expr_end]:
            return source[: match.start()] + source[match.end() :]
    return source


def strip_const_runtime_text_scaler(source: str) -> str:
    """Drop ``const`` before widgets that use ``MediaQuery.textScalerOf`` at runtime."""
    if _RUNTIME_TEXT_SCALER_MARKER not in source:
        return source
    updated = source
    while True:
        stripped = _strip_one_const_around_runtime_text_scaler(updated)
        if stripped == updated:
            break
        updated = stripped
    return re.sub(
        r"(\breturn\s+)const\s+(?=\w+\s*\()",
        r"\1",
        updated,
    )


def _split_top_level_commas(segment: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    start = 0
    for index, char in enumerate(segment):
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
        if char in "([{":
            depth += 1
            continue
        if char in ")]}":
            depth -= 1
            continue
        if char == "," and depth == 0:
            parts.append(segment[start:index])
            start = index + 1
    tail = segment[start:]
    if tail.strip():
        parts.append(tail)
    return parts


def repair_obsolete_dart_default_colons(source: str) -> str:
    """Rewrite pre-Dart 2.0 ``this.field : value`` defaults to ``this.field = value``."""
    return re.sub(
        r"(this\.\w+)\s*:\s*(?=['\"(\[\d])",
        r"\1 = ",
        source,
    )


def sanitize_named_only_widget_calls(
    source: str,
    *,
    widget_names: tuple[str, ...],
) -> str:
    """Drop stray positional args on custom widgets that only accept named parameters."""
    updated = source
    for widget_name in widget_names:
        opener = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(widget_name)}\s*\(")
        index = 0
        parts: list[str] = []
        while True:
            match = opener.search(updated, index)
            if match is None:
                parts.append(updated[index:])
                break
            start = match.start()
            parts.append(updated[index:start])
            paren_start = match.end() - 1
            paren_end = find_matching_paren(updated, paren_start)
            if paren_end is None:
                parts.append(updated[start:])
                break
            inner = updated[paren_start + 1 : paren_end]
            inner_stripped = inner.strip()
            if inner_stripped.startswith("{"):
                parts.append(updated[start : paren_end + 1])
                index = paren_end + 1
                continue
            if re.search(r"\b(?:required\s+)?this\.\w+", inner_stripped):
                parts.append(updated[start : paren_end + 1])
                index = paren_end + 1
                continue
            segments = _split_top_level_commas(inner)
            named = [segment.strip() for segment in segments if segment.strip() and ":" in segment]
            if not named:
                parts.append(f"{widget_name}(onPressed: () {{}})")
            else:
                if not any(segment.startswith("onPressed") for segment in named):
                    named.insert(0, "onPressed: () {}")
                parts.append(f"{widget_name}({', '.join(named)})")
            index = paren_end + 1
        updated = "".join(parts)
    return updated
