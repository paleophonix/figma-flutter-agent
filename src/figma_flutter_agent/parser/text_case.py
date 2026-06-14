"""Figma ``textCase`` style transforms for deterministic display text."""

from __future__ import annotations

import re

from figma_flutter_agent.schemas.style import FigmaTextCase

_TITLE_WORD = re.compile(r"([^\W_]+)", flags=re.UNICODE)


def apply_figma_text_case(text: str, text_case: FigmaTextCase | str | None) -> str:
    """Apply Figma ``textCase`` to visible copy while preserving newlines.

    ``SMALL_CAPS`` / ``SMALL_CAPS_FORCED`` are not rasterized in T0 emit; the
    source string is returned unchanged until font-feature support exists.
    """
    if not text or not text_case or text_case == "ORIGINAL":
        return text
    if text_case == "UPPER":
        return text.upper()
    if text_case == "LOWER":
        return text.lower()
    if text_case == "TITLE":
        lines = text.split("\n")
        return "\n".join(_title_case_line(line) for line in lines)
    return text


def _title_case_line(line: str) -> str:
    return _TITLE_WORD.sub(lambda match: match.group(0).title(), line)
