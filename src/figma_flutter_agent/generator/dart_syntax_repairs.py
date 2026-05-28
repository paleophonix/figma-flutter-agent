"""Lightweight Dart syntax repairs without ast_sidecar imports."""

from __future__ import annotations

import re

_DUPLICATE_CHILD_PARAM_RE = re.compile(r"(\bchild:\s*)+child:\s*", re.IGNORECASE)
_MISPLACED_CHILD_BEFORE_NAMED_RE = re.compile(
    r"\bchild:\s+(?=(?:key|onPressed|backgroundColor|textColor|text|icon|border|required|super)\b\s*:)",
    re.IGNORECASE,
)


def collapse_duplicate_child_named_params(source: str) -> str:
    """Collapse LLM stutter ``child: child: …`` into a single ``child:``."""
    updated = source
    while True:
        collapsed = _DUPLICATE_CHILD_PARAM_RE.sub("child: ", updated)
        if collapsed == updated:
            return updated
        updated = collapsed


def fix_misplaced_child_before_named_params(source: str) -> str:
    """Rewrite LLM ``child: key:`` / ``child: onPressed:`` stutter to valid named params."""
    return _MISPLACED_CHILD_BEFORE_NAMED_RE.sub("", source)


def apply_llm_dart_syntax_repairs(source: str) -> str:
    """Run deterministic repairs for common LLM Dart call-site mistakes."""
    updated = collapse_duplicate_child_named_params(source)
    return fix_misplaced_child_before_named_params(updated)
