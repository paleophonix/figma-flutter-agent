"""Labeled user-message formatting for LLM calls (generate, repair, refine)."""

from __future__ import annotations

import json
import re
from typing import Any

_SECTION_PATTERN = re.compile(r"^### ([^\n]+)\n(.*?)(?=^### |\Z)", re.MULTILINE | re.DOTALL)


def format_labeled_user_payload(
    *,
    mode: str,
    output_schema: str,
    sections: dict[str, Any],
) -> str:
    """Format user message with labeled ``###`` sections containing JSON bodies.

    Args:
        mode: Pipeline mode identifier (``generate``, ``repair_patch``, ``visual_refine``).
        output_schema: Short description of required structured output schema.
        sections: Top-level input fields; each becomes one ``### {key}`` block.

    Returns:
        User message text for the LLM (not a system prompt).
    """
    lines = [
        "## LLM input contract",
        f"Pipeline mode: {mode}.",
        f"Required output: {output_schema}",
        "Authoritative compiler input follows as labeled ### sections (JSON).",
        "Do not emit markdown code fences or free-text outside the API schema.",
        "",
    ]
    for key, value in sections.items():
        lines.append(f"### {key}")
        lines.append(json.dumps(value, ensure_ascii=False, indent=2))
        lines.append("")
    return "\n".join(lines).strip()


def parse_labeled_user_payload(text: str) -> dict[str, Any]:
    """Parse a labeled user payload back into a dictionary (for tests and tooling).

    Args:
        text: User message produced by ``format_labeled_user_payload``.

    Returns:
        Mapping of section titles to decoded JSON values.
    """
    result: dict[str, Any] = {}
    for match in _SECTION_PATTERN.finditer(text):
        key = match.group(1).strip()
        body = match.group(2).strip()
        if body:
            result[key] = json.loads(body)
    return result
