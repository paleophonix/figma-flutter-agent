"""In-process layout strip rules (parity with ``tools/dart_ast_sidecar`` structural rules)."""

from __future__ import annotations

import re
from typing import Any, Literal

from figma_flutter_agent.generator.dart.delimiter_expression import find_expression_end
from figma_flutter_agent.generator.dart.delimiters import find_matching_paren
from figma_flutter_agent.generator.dart.layout_extract import (
    extract_responsive_layout_builder_stack,
)

StructuralLayoutRule = Literal[
    "unwrap_scale_layout_builder",
    "strip_viewport_scale_transform",
]

_LAYOUT_BUILDER_RE = re.compile(r"LayoutBuilder\s*\(\s*builder:\s*\(")
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


def strip_responsive_layout_builder(source: str) -> str:
    updated = source
    search_from = 0
    while True:
        match = _LAYOUT_BUILDER_RE.search(updated, search_from)
        if match is None:
            break
        open_paren = updated.index("(", match.start())
        close_paren = find_matching_paren(updated, open_paren)
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


def strip_viewport_scale_transform(source: str) -> str:
    updated = source
    search_from = 0
    while True:
        match = _SCREEN_SCALE_TRANSFORM_RE.search(updated, search_from)
        if match is None:
            break
        match_start = match.start()
        open_paren = updated.index("(", match_start)
        close_paren = find_matching_paren(updated, open_paren)
        if close_paren is None:
            break
        inner = updated[open_paren + 1 : close_paren]
        child_match = re.search(r"\bchild:\s*", inner)
        if child_match is None:
            search_from = close_paren + 1
            continue
        child_start = open_paren + 1 + child_match.end()
        while child_start < len(updated) and updated[child_start].isspace():
            child_start += 1
        child_end = find_expression_end(updated, child_start)
        if child_end is None:
            search_from = close_paren + 1
            continue
        child_expr = updated[child_start:child_end].strip()
        updated = updated[:match_start] + child_expr + updated[close_paren + 1 :]
        search_from = match_start + len(child_expr)
    updated = _SCREEN_SCALE_DECL_RE.sub("", updated)
    updated = _SCREEN_WIDTH_FOR_SCALE_DECL_RE.sub("", updated)
    return updated


def apply_python_structural_layout_rules(
    source: str,
    rules: tuple[StructuralLayoutRule, ...],
) -> tuple[str, list[dict[str, Any]]]:
    updated = source
    edits: list[dict[str, Any]] = []
    if "unwrap_scale_layout_builder" in rules:
        before = updated
        updated = strip_responsive_layout_builder(updated)
        if updated != before:
            edits.append({"rule": "unwrap_scale_layout_builder"})
    if "strip_viewport_scale_transform" in rules:
        before = updated
        updated = strip_viewport_scale_transform(updated)
        if updated != before:
            edits.append({"rule": "strip_viewport_scale_transform"})
    return updated, edits
