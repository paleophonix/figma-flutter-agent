"""LayoutBuilder stack extraction for ambient-background merge (AST sidecar preferred)."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart_delimiters import (
    find_expression_end,
    find_matching_brace,
    find_matching_paren,
)
from figma_flutter_agent.generator.dart_unscale import unscale_design_expressions

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


def _unwrap_single_child_widget(expr: str) -> str:
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
            close_paren = find_matching_paren(current, open_paren)
            if close_paren is None:
                return current
            inner = current[open_paren + 1 : close_paren]
            child_match = re.search(r"\bchild:\s*", inner)
            if child_match is None:
                return current
            child_start = open_paren + 1 + child_match.end()
            while child_start < len(current) and current[child_start].isspace():
                child_start += 1
            child_end = find_expression_end(current, child_start)
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
    expr_end = find_expression_end(builder_body, return_start)
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
    params_close = find_matching_paren(layout_builder_block, params_open)
    if params_close is None:
        return None
    body_index = params_close + 1
    while body_index < len(layout_builder_block) and layout_builder_block[body_index] in " \t\n\r":
        body_index += 1
    if body_index >= len(layout_builder_block) or layout_builder_block[body_index] != "{":
        return None
    body_close = find_matching_brace(layout_builder_block, body_index)
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
