"""Syntax and delimiter repair passes for planned Dart files."""

from __future__ import annotations

from .paths import planned_content_for_path


def sanitize_screen_emit_syntax(content: str) -> str:
    """Repair common screen emit issues (misplaced TextStyle params, delimiters)."""
    from figma_flutter_agent.generator.dart.postprocess import inline_orphan_text_scaler_refs
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        apply_planned_delimiter_balance,
        fix_children_list_orphan_text_scaler,
        fix_garbage_closers_after_link_rich,
        fix_text_align_comma_semicolon,
        wrap_misplaced_text_style_params_on_text,
    )

    content = fix_garbage_closers_after_link_rich(content)
    content = fix_children_list_orphan_text_scaler(content)
    content = fix_text_align_comma_semicolon(content)
    content = inline_orphan_text_scaler_refs(content)
    content = wrap_misplaced_text_style_params_on_text(content)
    return apply_planned_delimiter_balance(content, force=True)


def _sanitize_screen_dart_syntax(content: str) -> str:
    """Repair delimiter drift on screen files via the AST sidecar."""
    return sanitize_screen_emit_syntax(content)


def _sanitize_widget_dart_syntax(content: str) -> str:
    from figma_flutter_agent.generator.dart.syntax_repairs import sanitize_planned_widget_syntax

    return sanitize_planned_widget_syntax(content)


def _sanitize_planned_dart_syntax(path: str, content: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.endswith("_screen.dart"):
        return _sanitize_screen_dart_syntax(content)
    if normalized.startswith("lib/widgets/") and normalized.endswith(".dart"):
        return _sanitize_widget_dart_syntax(content)
    return content


def _balance_planned_widget_delimiters(planned: dict[str, str]) -> dict[str, str]:
    """Repair delimiter drift on feature screens and extracted widget files."""
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        apply_planned_delimiter_balance,
        sanitize_planned_widget_syntax,
    )

    updated = dict(planned)
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        is_screen = normalized.startswith("lib/features/") and normalized.endswith(
            "_screen.dart"
        )
        is_widget = normalized.startswith("lib/widgets/") and normalized.endswith(".dart")
        if not is_screen and not is_widget:
            continue
        if validate_dart_delimiters(content) is None:
            continue
        repaired = (
            sanitize_planned_widget_syntax(content)
            if is_widget
            else apply_planned_delimiter_balance(content)
        )
        if repaired != content:
            updated[path] = repaired
    return updated


def repair_planned_misplaced_text_style_params(
    planned: dict[str, str],
    analyze_errors: tuple[str, ...] | list[str] = (),
) -> dict[str, str]:
    """Wrap ``Text(fontSize: …)`` mistakes (with or without a partial ``style:``)."""
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        wrap_misplaced_text_style_params_on_text,
    )

    style_param_errors = (
        "fontSize' isn't defined",
        "fontWeight' isn't defined",
        "letterSpacing' isn't defined",
        "fontFamilyFallback' isn't defined",
    )
    force_all = not analyze_errors or any(
        any(token in error for token in style_param_errors) for error in analyze_errors
    )
    if not force_all:
        return planned

    updated = dict(planned)
    for path, content in planned.items():
        if not path.endswith(".dart"):
            continue
        repaired = wrap_misplaced_text_style_params_on_text(content)
        if repaired != content:
            updated[path] = repaired
    return updated


def repair_planned_format_parse_failures(
    planned: dict[str, str],
    format_paths: tuple[str, ...],
    *,
    analyze_errors: tuple[str, ...] = (),
    repair_pass: int = 0,
) -> dict[str, str]:
    """Deterministic cleanup when ``dart format`` cannot parse planned Dart (e.g. ``])))}}``)."""
    if not format_paths:
        return planned
    from figma_flutter_agent.generator.dart.llm_codegen import (
        repair_dart_delimiters,
        trim_surplus_dart_delimiters,
        validate_dart_delimiters,
    )
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        append_missing_closers_on_lines,
        apply_format_parse_error_insertions,
        apply_planned_delimiter_balance,
        is_garbage_closer_only_line,
        is_orphan_semicolon_line,
        parse_format_error_line_numbers,
        sanitize_planned_widget_syntax,
    )

    def _format_errors_suggest_delimiters() -> bool:
        tokens = (
            "Expected to find ']'",
            "Expected to find '}'",
            "Expected to find ')'",
            "Expected to find ','",
            "Expected to find ';'",
        )
        return any(any(token in error for token in tokens) for error in analyze_errors)

    def _repair_format_parse_source(text: str, *, normalized_path: str) -> str:
        if analyze_errors:
            text = apply_format_parse_error_insertions(
                text,
                analyze_errors,
                attempt=repair_pass,
            )
        if error_lines:
            text = append_missing_closers_on_lines(text, error_lines)
        trimmed = trim_surplus_dart_delimiters(text)
        if trimmed is not None:
            text = trimmed
        if normalized_path.endswith("_screen.dart") or (
            _format_errors_suggest_delimiters()
            and normalized_path.startswith("lib/widgets/")
            and normalized_path.endswith(".dart")
        ):
            text = sanitize_screen_emit_syntax(text)
        text = repair_dart_delimiters(text)
        if validate_dart_delimiters(text) is not None:
            text = apply_planned_delimiter_balance(text, force=True)
            text = repair_dart_delimiters(text)
        return repair_dart_delimiters(text)

    error_lines = parse_format_error_line_numbers(analyze_errors)
    for path in format_paths:
        located = planned_content_for_path(planned, path)
        if located is None:
            continue
        normalized, content = located
        lines = content.splitlines()
        if error_lines:
            for line_no in error_lines:
                index = line_no - 1
                if 0 <= index < len(lines) and (
                    is_garbage_closer_only_line(lines[index])
                    or is_orphan_semicolon_line(lines[index])
                ):
                    lines[index] = ""
            text = "\n".join(lines)
        else:
            text = content
        repaired = _repair_format_parse_source(text, normalized_path=normalized)
        if normalized.startswith("lib/widgets/") and normalized.endswith(".dart"):
            repaired = sanitize_planned_widget_syntax(repaired)
        if repaired != content:
            planned[normalized] = repaired
            for key in list(planned):
                if key != normalized and key.replace("\\", "/") == normalized:
                    del planned[key]
    return planned
