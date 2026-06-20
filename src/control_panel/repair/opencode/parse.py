"""Extract assistant text from OpenCode message response."""

from __future__ import annotations

import json
from typing import Any

from control_panel.repair.evaluation import DiagnoseOpinion


def extract_text(response: dict[str, Any]) -> str:
    """Concatenate text parts from an OpenCode message response."""
    chunks: list[str] = []
    parts = response.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                chunks.append(str(part.get("text") or ""))
    info = response.get("info")
    if isinstance(info, dict):
        structured = info.get("structured_output")
        if structured is not None:
            chunks.append(json.dumps(structured, ensure_ascii=False))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def parse_diagnose_opinion(text: str, *, role: str = "diagnose") -> DiagnoseOpinion:
    """Parse diagnose JSON or fall back to free-form text."""
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
            return DiagnoseOpinion(
                role=role,
                root_cause=str(data.get("root_cause") or ""),
                confidence=float(data.get("confidence") or 0.5),
                recommended_law=str(data.get("recommended_law") or ""),
                escalate=bool(data.get("escalate")),
            )
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return DiagnoseOpinion(
        role=role,
        root_cause=text[:500],
        confidence=0.4,
        recommended_law="",
        escalate=False,
    )
