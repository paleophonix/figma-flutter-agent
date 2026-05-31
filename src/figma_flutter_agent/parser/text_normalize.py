"""Normalize Figma TEXT ``characters`` before clean-tree codegen."""

from __future__ import annotations

import re

_MULTI_SPACE_BEFORE_NL = re.compile(r"[ \t]+\n")


def normalize_figma_characters(text: str) -> str:
    """Collapse stray spaces before line breaks and trim trailing whitespace."""
    if not text:
        return text
    normalized = _MULTI_SPACE_BEFORE_NL.sub("\n", text)
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).rstrip()
