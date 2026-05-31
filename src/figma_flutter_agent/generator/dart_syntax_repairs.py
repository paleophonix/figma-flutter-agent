"""Dart syntax repairs — delimiter balance and LLM fixes via the AST sidecar."""

from __future__ import annotations

import re

from loguru import logger

_FORMAT_ERROR_LINE_RE = re.compile(r"^line (\d+), column \d+ of ")

_PLANNED_DELIMITER_BALANCE_RULES: tuple[str, ...] = ("planned_delimiter_balance",)


def apply_planned_delimiter_balance(source: str) -> str:
    """Balance planned/emit Dart delimiters through the native AST sidecar."""
    from figma_flutter_agent.tools.ast_sidecar import AstSidecarError, apply_ast_rules

    result = apply_ast_rules(
        source,
        _PLANNED_DELIMITER_BALANCE_RULES,
        include_text_scaler=False,
    )
    rule_names = {str(edit.get("rule", "")) for edit in result.edits}
    if "planned_delimiter_balance" not in rule_names and result.source == source:
        raise AstSidecarError(
            "AST sidecar did not run planned_delimiter_balance "
            "(rebuild tools/bin/ast_compiler.exe or set FIGMA_FLUTTER_SDK)"
        )
    return result.source


def sanitize_emit_screen_syntax(source: str) -> str:
    """Deterministic bracket repairs for planned/LLM screen ``build`` bodies."""
    return apply_planned_delimiter_balance(source)


def repair_planned_dart_delimiters_if_needed(source: str) -> str:
    """Run AST delimiter balance when structural validation fails."""
    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

    if validate_dart_delimiters(source) is None:
        return source
    balanced = apply_planned_delimiter_balance(source)
    if validate_dart_delimiters(balanced) is None:
        return balanced
    return source


def sanitize_planned_widget_syntax(source: str) -> str:
    """Sanitize planned ``lib/widgets`` Dart before format/analyze."""
    return apply_planned_delimiter_balance(source)


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


def fix_garbage_closers_after_link_rich(source: str) -> str:
    """Deprecated: use :func:`apply_planned_delimiter_balance`."""
    return apply_planned_delimiter_balance(source)
