"""Design-coordinate unscale helpers (shared by layout strip and AST reconcile)."""

from __future__ import annotations

import re


def unscale_design_expressions(source: str) -> str:
    """Replace ``287.0 * scaleY``-style LLM responsive math with fixed design coordinates."""
    updated = source
    for pattern in (
        r"(\d+(?:\.\d+)?)\s*\*\s*scaleX\b",
        r"(\d+(?:\.\d+)?)\s*\*\s*scaleY\b",
        r"(\d+(?:\.\d+)?)\s*\*\s*scale\b",
    ):
        updated = re.sub(pattern, r"\1", updated)
    updated = re.sub(
        r"width:\s*constraints\.maxWidth\b",
        "width: designWidth",
        updated,
    )
    updated = re.sub(
        r"height:\s*designHeight\s*\*\s*scaleY\b",
        "height: designHeight",
        updated,
    )
    return updated
