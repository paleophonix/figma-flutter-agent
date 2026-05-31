"""Dart syntax repairs — delegated to the AST sidecar (``tools/dart_ast_sidecar``)."""

from __future__ import annotations

import re

_FORMAT_ERROR_LINE_RE = re.compile(r"^line (\d+), column \d+ of ")
_LINK_RICH_GARBAGE_CLOSE = ")))])))),"
_LINK_RICH_GARBAGE_CLOSE_FIXED = ")))]))),"
_LOG_IN_RICH_GARBAGE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "textScaler: textScaler,\n"
        "                            textAlign: TextAlign.left)),\n"
        "                  )))])))), Positioned(left: 58.0, child: Text('next')),",
        "textScaler: textScaler,\n"
        "                            textAlign: TextAlign.left,\n"
        "                          ),\n"
        "                        ),\n"
        "                      ),\n"
        "                    ),\n"
        "                  ),\n"
        "                ),\n"
        "              ],\n"
        "            ),\n"
        "          ),\n"
        "        ),\n"
        "      ),\n"
        "      Positioned(left: 58.0, child: Text('next')),",
    ),
    (
        "textScaler: textScaler, textAlign: TextAlign.left)),\n                  )))]))),",
        "textScaler: textScaler, textAlign: TextAlign.left)),\n                  ))), ]))),",
    ),
    (
        "textAlign: TextAlign.left)), )))]))), Positioned",
        "textAlign: TextAlign.left)), )), Positioned",
    ),
    (
        "textScaler: textScaler, textAlign: TextAlign.left)), )))]))), Positioned",
        "textScaler: textScaler, textAlign: TextAlign.left)), )), Positioned",
    ),
    (
        "textAlign: TextAlign.left))), )))])))), Positioned",
        "textAlign: TextAlign.left), Positioned",
    ),
    (
        "textAlign: TextAlign.left)), )))])))), Positioned",
        "textAlign: TextAlign.left), Positioned",
    ),
    (
        "textAlign: TextAlign.left))), )))]))), Positioned",
        "textAlign: TextAlign.left), Positioned",
    ),
    (
        "textAlign: TextAlign.left)),\n                  )))])))), Positioned(left: 58.0",
        "textAlign: TextAlign.left)),\n                  ))), ]), ), ), Positioned(left: 58.0",
    ),
    (
        "textAlign: TextAlign.left)),\n                  )))])))), Positioned(left: 58.0, child: Text('next')),",
        "textAlign: TextAlign.left)),\n                  ))), ]), ), ), Positioned(left: 58.0, child: Text('next')),",
    ),
    (
        "textAlign: TextAlign.left))),\n                  )))]))), Positioned",
        "textAlign: TextAlign.left)),\n                  )), Positioned",
    ),
    (
        "textAlign: TextAlign.left))), )))]))), Positioned",
        "textAlign: TextAlign.left)), )), Positioned",
    ),
    (
        "left)), )))])))), Positioned",
        "left)), ))), ]))), Positioned",
    ),
    (
        "left)), )))]))), Positioned",
        "left)), ))), ]))), Positioned",
    ),
    (
        ")))])), Positioned",
        "))), Positioned",
    ),
    (
        "textAlign: TextAlign.center),\n                  )))])), Positioned",
        "textAlign: TextAlign.center),\n                  )), Positioned",
    ),
)
_EXTRA_CLOSE_AFTER_CENTER_TEXT = re.compile(
    r"(textAlign: TextAlign\.center\)),\s*\n\s*\)\),",
)
_EXTRA_CLOSE_AFTER_CENTER_TEXT_MINIFIED = re.compile(
    r"(textAlign: TextAlign\.center\)),\s*\)\),",
)
_TRANSPARENT_MATERIAL_OPEN = re.compile(
    r"Material\(\s*type:\s*MaterialType\.transparency,\s*child:\s*",
    re.MULTILINE,
)


def _advance_past_dart_string(source: str, index: int) -> int:
    quote = source[index]
    if quote not in "'\"":
        return index
    position = index + 1
    length = len(source)
    while position < length:
        char = source[position]
        if char == "\\":
            position += 2
            continue
        if char == quote:
            return position + 1
        position += 1
    return length


def unwrap_transparent_material_wrappers(source: str) -> str:
    """Unwrap LLM ``Material(type: MaterialType.transparency)`` around tappable text."""
    parts: list[str] = []
    last = 0
    for match in _TRANSPARENT_MATERIAL_OPEN.finditer(source):
        parts.append(source[last : match.start()])
        child_start = match.end()
        length = len(source)
        open_at = source.find("(", child_start)
        if open_at < 0:
            parts.append(source[match.start() :])
            return "".join(parts)
        depth = 0
        index = open_at
        while index < length:
            char = source[index]
            if char in "'\"":
                index = _advance_past_dart_string(source, index)
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    index += 1
                    parts.append(source[child_start:index])
                    last = index
                    while last < length and source[last] in " \t\n\r":
                        last += 1
                    if last < length and source[last] == ")":
                        last += 1
                    break
            index += 1
        else:
            parts.append(source[match.start() :])
            return "".join(parts)
    parts.append(source[last:])
    return "".join(parts)


def fix_garbage_closers_after_link_rich(source: str) -> str:
    """Repair surplus closers after tappable ``Text.rich`` in button stacks."""
    out = source
    for broken, fixed in _LOG_IN_RICH_GARBAGE_REPLACEMENTS:
        out = out.replace(broken, fixed)
    out = out.replace(_LINK_RICH_GARBAGE_CLOSE, _LINK_RICH_GARBAGE_CLOSE_FIXED)
    out = _EXTRA_CLOSE_AFTER_CENTER_TEXT.sub(r"\1),\n                  ),", out)
    out = _EXTRA_CLOSE_AFTER_CENTER_TEXT_MINIFIED.sub(r"\1), ),", out)
    return out


def sanitize_emit_screen_syntax(source: str) -> str:
    """Deterministic bracket repairs for planned/LLM screen ``build`` bodies."""
    text = fix_garbage_closers_after_link_rich(source)
    text = strip_orphan_semicolon_only_lines(text)
    text = strip_garbage_closer_only_lines(text)
    text = fix_garbage_closers_after_link_rich(text)
    lines = [line for line in text.splitlines() if not re.match(r"^\s*,\s*$", line)]
    text = "\n".join(lines)
    return re.sub(r"\n(\s*);\s*\n(\s*[\]\)])", r"\n\2", text)


def _strip_duplicate_statement_semicolons(source: str) -> str:
    """Collapse ``);;`` / ``._();;`` artifacts from AST or hand edits."""
    return re.sub(r";(\s*);", ";", source)


def repair_planned_dart_delimiters_if_needed(source: str) -> str:
    """Repair delimiter drift only when invalid; never append garbage closers."""
    from figma_flutter_agent.generator.llm_dart import repair_dart_delimiters, validate_dart_delimiters

    text = _strip_duplicate_statement_semicolons(source)
    if validate_dart_delimiters(text) is None:
        return text
    repaired = repair_dart_delimiters(text)
    if any(marker in repaired for marker in (";\n]))", "}}")):
        return text
    if validate_dart_delimiters(repaired) is None:
        return repaired
    return text


def sanitize_planned_widget_syntax(source: str) -> str:
    """Sanitize planned ``lib/widgets`` Dart before format/analyze."""
    text = _strip_duplicate_statement_semicolons(source)
    text = strip_orphan_semicolon_only_lines(text)
    text = strip_garbage_closer_only_lines(text)
    return repair_planned_dart_delimiters_if_needed(text)


def _apply_via_sidecar(source: str) -> str:
    from figma_flutter_agent.tools.ast_sidecar import apply_ast_rules

    return apply_ast_rules(
        source,
        ("llm_syntax_repairs",),
        include_text_scaler=False,
    ).source


def collapse_duplicate_child_named_params(source: str) -> str:
    return _apply_via_sidecar(source)


def fix_misplaced_child_before_named_params(source: str) -> str:
    return _apply_via_sidecar(source)


def is_garbage_closer_only_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return len(stripped) >= 2 and all(ch in "])}" for ch in stripped)


def is_orphan_semicolon_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and all(ch == ";" for ch in stripped)


def strip_orphan_semicolon_only_lines(source: str) -> str:
    return _apply_via_sidecar(source)


def normalize_app_typography_style_references(source: str) -> str:
    return _apply_via_sidecar(source)


def strip_duplicate_key_after_super(source: str) -> str:
    return _apply_via_sidecar(source)


def use_scale_down_for_design_canvas_fittedbox(source: str) -> str:
    return _apply_via_sidecar(source)


def fix_elevated_button_label_on_saturated_background(source: str) -> str:
    return _apply_via_sidecar(source)


def wrap_misplaced_text_style_params_on_text(source: str) -> str:
    return _apply_via_sidecar(source)


def strip_garbage_closer_only_lines(source: str) -> str:
    return _apply_via_sidecar(source)


def parse_format_error_line_numbers(errors: tuple[str, ...] | list[str]) -> tuple[int, ...]:
    numbers: list[int] = []
    for error in errors:
        match = _FORMAT_ERROR_LINE_RE.match(error.strip())
        if match is not None:
            numbers.append(int(match.group(1)))
    return tuple(dict.fromkeys(numbers))


def replace_image_network_calls(source: str) -> str:
    return _apply_via_sidecar(source)


def fix_misused_flex_widget_name(source: str) -> str:
    return _apply_via_sidecar(source)


def apply_llm_dart_syntax_repairs(source: str) -> str:
    """Run the full LLM syntax repair pass via the Dart AST sidecar."""
    return _apply_via_sidecar(source)
