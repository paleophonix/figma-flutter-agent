"""Design-coordinate unscale helpers (shared by layout strip and AST reconcile)."""

from __future__ import annotations

import re


_DESIGN_WIDTH_DECL_RE = re.compile(r"\b(?:const|final|static)\s+double\s+designWidth\b")
_DESIGN_HEIGHT_DECL_RE = re.compile(r"\b(?:const|final|static)\s+double\s+designHeight\b")


def unscale_design_expressions(source: str) -> str:
    """Replace ``287.0 * scaleY``-style LLM responsive math with fixed design coordinates."""
    updated = source
    for pattern in (
        r"(\d+(?:\.\d+)?)\s*\*\s*scaleX\b",
        r"(\d+(?:\.\d+)?)\s*\*\s*scaleY\b",
        r"(\d+(?:\.\d+)?)\s*\*\s*scale\b",
    ):
        updated = re.sub(pattern, r"\1", updated)
    if _DESIGN_WIDTH_DECL_RE.search(updated):
        updated = re.sub(
            r"width:\s*constraints\.maxWidth\b",
            "width: designWidth",
            updated,
        )
    if _DESIGN_HEIGHT_DECL_RE.search(updated):
        updated = re.sub(
            r"height:\s*designHeight\s*\*\s*scaleY\b",
            "height: designHeight",
            updated,
        )
    return updated


def repair_orphan_design_canvas_identifiers(source: str) -> str:
    """Rewrite orphan ``designWidth`` / ``designHeight`` refs when no canvas const exists."""
    if "designWidth" not in source and "designHeight" not in source:
        return source
    updated = source
    if not _DESIGN_WIDTH_DECL_RE.search(updated):
        updated = re.sub(r"\bdesignWidth\b", "constraints.maxWidth", updated)
    if not _DESIGN_HEIGHT_DECL_RE.search(updated):
        updated = re.sub(r"\bdesignHeight\b", "constraints.maxHeight", updated)
    return updated
