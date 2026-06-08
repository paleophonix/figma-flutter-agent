"""Runtime textScaler const repairs."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.delimiters import find_matching_bracket, find_matching_paren
from figma_flutter_agent.tools.ast_sidecar import apply_ast_rules, ast_source_exceeds_sidecar_limit

ORPHAN_TEXT_SCALER_REF_RE = re.compile(r"\btextScaler:\s*textScaler\b")
TEXT_SCALER_DECL_RE = re.compile(r"(?:final|var)\s+textScaler\s*=\s*MediaQuery\.textScalerOf\(")
RUNTIME_TEXT_SCALER_MARKER = "textScaler: MediaQuery.textScalerOf("
CONST_KEYWORD_RE = re.compile(r"\bconst\s+")


def ensure_text_scaler_support(source: str) -> str:
    if ast_source_exceeds_sidecar_limit(source):
        return inline_orphan_text_scaler_refs(source)
    return apply_ast_rules(source, (), include_text_scaler=True).source


def inline_orphan_text_scaler_refs(source: str, *, context: str = "context") -> str:
    """Fallback when AST cannot fix layout-spliced ``textScaler: textScaler`` references."""
    if not ORPHAN_TEXT_SCALER_REF_RE.search(source):
        return source
    if TEXT_SCALER_DECL_RE.search(source):
        return source
    return ORPHAN_TEXT_SCALER_REF_RE.sub(
        f"textScaler: MediaQuery.textScalerOf({context})",
        source,
    )


def const_expression_end(source: str, start: int) -> int | None:
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


def strip_one_const_around_runtime_text_scaler(source: str) -> str:
    for match in reversed(list(CONST_KEYWORD_RE.finditer(source))):
        expr_start = match.end()
        expr_end = const_expression_end(source, expr_start)
        if expr_end is None:
            continue
        if RUNTIME_TEXT_SCALER_MARKER in source[expr_start:expr_end]:
            return source[: match.start()] + source[match.end() :]
    return source


def strip_const_runtime_text_scaler(source: str) -> str:
    """Drop ``const`` before widgets that use ``MediaQuery.textScalerOf`` at runtime."""
    if RUNTIME_TEXT_SCALER_MARKER not in source:
        return source
    updated = source
    while True:
        stripped = strip_one_const_around_runtime_text_scaler(updated)
        if stripped == updated:
            break
        updated = stripped
    return re.sub(
        r"(\breturn\s+)const\s+(?=\w+\s*\()",
        r"\1",
        updated,
    )
