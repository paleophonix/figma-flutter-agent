"""Dart syntax repairs — delimiter balance and LLM fixes via the AST sidecar."""

from __future__ import annotations

import re

_FORMAT_ERROR_LINE_RE = re.compile(r"^line (\d+), column \d+ of ")
_FORMAT_ERROR_INSERT_RE = re.compile(
    r"line (\d+), column (\d+) of .+?: Expected to find '([^']+)'"
)

_LARGE_WIDGET_SYNTAX_BYTES = 200_000


def _apply_via_sidecar(source: str) -> str:
    from figma_flutter_agent.tools.ast_sidecar import (
        apply_ast_rules,
        ast_source_exceeds_sidecar_limit,
    )

    if ast_source_exceeds_sidecar_limit(source):
        return source

    return apply_ast_rules(
        source,
        ("llm_syntax_repairs",),
        include_text_scaler=False,
    ).source


def _apply_planned_balance_rule(source: str) -> str:
    from figma_flutter_agent.tools.ast_sidecar import (
        apply_ast_rules,
        ast_source_exceeds_sidecar_limit,
    )

    if ast_source_exceeds_sidecar_limit(source):
        return source

    return apply_ast_rules(
        source,
        ("planned_delimiter_balance",),
        include_text_scaler=False,
    ).source


def _delimiter_validation_error(source: str) -> str | None:
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    return validate_dart_delimiters(source)


def is_orphan_comma_line(line: str) -> bool:
    return line.strip() == ","


def _needs_planned_delimiter_balance(source: str) -> bool:
    if _delimiter_validation_error(source) is not None:
        return True
    return any(is_orphan_comma_line(line) for line in source.splitlines())


def apply_planned_delimiter_balance(source: str, *, force: bool = False) -> str:
    """Balance planned/emit Dart delimiters (one prebuilt AST pass when needed)."""
    if not force and not _needs_planned_delimiter_balance(source):
        return source
    return _apply_planned_balance_rule(source)


def sanitize_emit_screen_syntax(source: str) -> str:
    """Deterministic bracket repairs for planned/LLM screen ``build`` bodies."""
    return apply_planned_delimiter_balance(source)


def repair_planned_dart_delimiters_if_needed(source: str) -> str:
    """Run AST delimiter balance when structural validation fails."""
    return apply_planned_delimiter_balance(source)


def sanitize_planned_widget_syntax(source: str) -> str:
    """Sanitize planned ``lib/widgets`` Dart before format/analyze."""
    from figma_flutter_agent.generator.layout.navigation import (
        ensure_layout_chrome_nav_helpers,
    )

    source = ensure_layout_chrome_nav_helpers(source)
    if len(source.encode("utf-8")) > _LARGE_WIDGET_SYNTAX_BYTES:
        return source
    if _delimiter_validation_error(source) is None and ";;" not in source:
        return source
    return _apply_planned_balance_rule(source)


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


_BROKEN_TEXT_COPYWITH_ORPHAN = re.compile(
    r"Text\(\s*'([^']*)'\s*,\s*"
    r"style:\s*Theme\.of\(context\)\.textTheme\.(\w+)\?\.copyWith\(\s*"
    r"color:\s*(Color\(0x[0-9A-Fa-f]+\))\s*\)\s*,\s*"
    r"(?:textScaler:\s*MediaQuery\.textScalerOf\(context\)\)\s*,\s*)+"
    r"textScaler:\s*MediaQuery\.textScalerOf\(context\)\)\)+\s*,\s*"
    r"(?P<style_tail>(?:(?:fontSize|fontWeight\]?|height|letterSpacing|leadingDistribution|textScaler)\s*:[^,\]]+,?\s*)+)"
    r"(?P<text_align>textAlign:\s*TextAlign\.\w+)\s*\]\)?",
    re.DOTALL,
)


def _fix_broken_text_copywith_orphan(match: re.Match[str]) -> str:
    label = match.group(1)
    typo = match.group(2)
    color = match.group(3)
    style_tail = match.group("style_tail").strip().rstrip(",")
    style_tail = style_tail.replace("fontWeight]:", "fontWeight:")
    style_tail = re.sub(
        r",?\s*textScaler:\s*(?:textScaler|MediaQuery\.textScalerOf\(context\)),?\s*",
        ", ",
        style_tail,
    ).strip(" ,")
    text_align = match.group("text_align")
    return (
        f"Text('{label}', style: Theme.of(context).textTheme.{typo}?.copyWith("
        f"color: {color}, {style_tail}), textScaler: MediaQuery.textScalerOf(context), "
        f"{text_align})"
    )


def merge_orphaned_text_style_params_after_close(source: str) -> str:
    """Move ``fontSize:`` / ``fontWeight:`` blocks that sit after ``Text(...)),`` into ``copyWith``."""
    return _BROKEN_TEXT_COPYWITH_ORPHAN.sub(_fix_broken_text_copywith_orphan, source)


_TEXT_ALIGN_SQUARE_BRACKET = re.compile(
    r"(textAlign:\s*TextAlign\.\w+)\s*\]",
)


def fix_text_align_square_bracket_close(source: str) -> str:
    """``textAlign: TextAlign.left]`` → ``...left)`` (common LLM emit typo)."""
    return _TEXT_ALIGN_SQUARE_BRACKET.sub(r"\1)", source)


_TEXT_ALIGN_COMMA_SEMICOLON = re.compile(r"(textAlign:\s*TextAlign\.\w+),\s*;")
_CHILDREN_ORPHAN_TEXT_SCALER = re.compile(
    r"children:\s*\[\s*textScaler:\s*textScaler\s*,\s*",
    re.MULTILINE,
)


def fix_text_align_comma_semicolon(source: str) -> str:
    """``textAlign: TextAlign.center,;`` → ``textAlign: TextAlign.center,``."""
    return _TEXT_ALIGN_COMMA_SEMICOLON.sub(r"\1,", source)


def fix_children_list_orphan_text_scaler(source: str) -> str:
    """``children: [textScaler: textScaler,`` → ``children: [``."""
    return _CHILDREN_ORPHAN_TEXT_SCALER.sub("children: [", source)


def wrap_misplaced_text_style_params_on_text(source: str) -> str:
    source = merge_orphaned_text_style_params_after_close(source)
    source = fix_text_align_square_bracket_close(source)
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


def append_missing_closers_on_lines(
    source: str,
    line_numbers: tuple[int, ...] | list[int],
) -> str:
    """Append missing ``)]}`` on specific lines (format errors often cite the broken line)."""
    if not line_numbers:
        return source
    from figma_flutter_agent.generator.dart.llm_codegen import _dart_delimiter_stack

    pairs = {"(": ")", "[": "]", "{": "}"}
    lines = source.splitlines()
    for line_no in line_numbers:
        index = line_no - 1
        if not 0 <= index < len(lines):
            continue
        stack = _dart_delimiter_stack(lines[index])
        if not stack:
            continue
        lines[index] = lines[index] + "".join(pairs[opener] for opener in reversed(stack))
    return "\n".join(lines)


def apply_format_parse_error_insertions(
    source: str,
    errors: tuple[str, ...] | list[str],
    *,
    attempt: int = 0,
) -> str:
    """Insert ``]`` / ``,`` / ``;`` at ``dart format`` error columns when the parser expected them."""
    insertions: list[tuple[int, int, str]] = []
    for error in errors:
        match = _FORMAT_ERROR_INSERT_RE.search(error)
        if match is None:
            continue
        line_no = int(match.group(1))
        column = int(match.group(2))
        expected = match.group(3)
        if expected in {"]", "}", ")", ",", ";"}:
            insertions.append((line_no, column, expected))
    if not insertions:
        return source

    lines = source.splitlines()
    by_line: dict[int, list[tuple[int, str]]] = {}
    for line_no, column, expected in insertions:
        by_line.setdefault(line_no, []).append((column, expected))

    for line_no, items in by_line.items():
        index = line_no - 1
        if not 0 <= index < len(lines):
            continue
        line = lines[index]
        for column, expected in sorted(items, key=lambda item: item[0], reverse=True):
            position = max(0, column - 1 - attempt)
            if position > len(line):
                line = f"{line}{expected}"
                continue
            if line[position : position + len(expected)] == expected:
                position = min(len(line), position + 1)
                if position > len(line) or line[position : position + len(expected)] == expected:
                    line = f"{line}{expected}"
                    continue
            line = f"{line[:position]}{expected}{line[position:]}"
        lines[index] = line
    return "\n".join(lines)


def replace_image_network_calls(source: str) -> str:
    return _apply_via_sidecar(source)


def fix_misused_flex_widget_name(source: str) -> str:
    return _apply_via_sidecar(source)


_BROKEN_ARTBOARD_DOUBLE_FROM_ENV = re.compile(
    r"(?:const|static\s+final)\s+double\s+(_artboardPreview(?:Width|Height))\s*=\s*"
    r"double\.fromEnvironment\s*\(\s*['\"](?P<define>[^'\"]+)['\"]\s*\)\s*;?",
    re.MULTILINE,
)


def repair_broken_artboard_preview_declarations(source: str) -> str:
    """Fix LLM-corrupted ``double.fromEnvironment`` artboard preview static fields."""
    if "double.fromEnvironment" not in source:
        return source

    def _replace(match: re.Match[str]) -> str:
        field = match.group(1)
        define = match.group("define")
        return (
            f"static final double {field} = double.tryParse(\n"
            f"    const String.fromEnvironment('{define}'),\n"
            f"  ) ??\n"
            f"  0;"
        )

    return _BROKEN_ARTBOARD_DOUBLE_FROM_ENV.sub(_replace, source)


def apply_llm_dart_syntax_repairs(source: str) -> str:
    """Run the full LLM syntax repair pass via the Dart AST sidecar."""
    return repair_broken_artboard_preview_declarations(_apply_via_sidecar(source))


def fix_garbage_closers_after_link_rich(source: str) -> str:
    return _apply_planned_balance_rule(source)


# ---------------------------------------------------------------------------
# Transparent-Material wrapper removal
# ---------------------------------------------------------------------------

_TRANSPARENT_MATERIAL_RE = re.compile(
    r"Material\(\s*\n?\s*type:\s*MaterialType\.transparency,\s*\n?\s*child:\s*",
    re.MULTILINE,
)


def unwrap_transparent_material_wrappers(source: str) -> str:
    """Remove ``Material(type: MaterialType.transparency, child: X)`` wrappers.

    The LLM sometimes emits redundant transparent Material wrappers around
    interactive widgets.  This function strips the wrapper keeping only the
    child expression; it does not affect Material widgets with a non-default
    type or with explicit color/elevation.

    Args:
        source: Raw Dart source fragment (may be a full file or a snippet).

    Returns:
        Source with transparent-Material wrappers replaced by their child.
    """
    return _TRANSPARENT_MATERIAL_RE.sub("", source)
