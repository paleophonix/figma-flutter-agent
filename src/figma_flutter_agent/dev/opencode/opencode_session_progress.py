"""Live OpenCode session progress summarization for wizard observability."""

from __future__ import annotations

from typing import Any

OPENCODE_PROGRESS_POLL_SEC = 8.0


def normalize_session_messages(payload: object) -> list[dict[str, Any]]:
    """Normalize OpenCode session message list payloads."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        nested = payload.get("messages")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return []


def summarize_opencode_progress(messages: list[dict[str, Any]]) -> str:
    """Build a short human-readable progress line from session messages.

    Args:
        messages: OpenCode ``GET /session/{id}/message`` payload.

    Returns:
        Progress summary for wizard console / repair logs.
    """
    tool_count = 0
    last_tool = ""
    for message in messages:
        parts = message.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict) or part.get("type") != "tool":
                continue
            tool_count += 1
            state = part.get("state")
            if not isinstance(state, dict):
                continue
            tool_name = str(part.get("tool") or "tool")
            status = str(state.get("status") or "").strip()
            raw_input = state.get("input")
            input_data = raw_input if isinstance(raw_input, dict) else {}
            target = (
                input_data.get("filePath")
                or input_data.get("path")
                or input_data.get("pattern")
                or input_data.get("command")
                or input_data.get("query")
            )
            if target:
                last_tool = f"{tool_name} {status} {target}".strip()
            else:
                last_tool = f"{tool_name} {status}".strip()

    if last_tool:
        return f"tools={tool_count} · {last_tool}"
    if tool_count:
        return f"tools={tool_count} · running"

    for message in reversed(messages):
        info = message.get("info")
        if not isinstance(info, dict):
            continue
        tokens = info.get("tokens")
        if not isinstance(tokens, dict):
            continue
        tokens_in = tokens.get("input")
        tokens_out = tokens.get("output")
        if tokens_in or tokens_out:
            return f"LLM tokens in={tokens_in or 0} out={tokens_out or 0}"

    if len(messages) <= 1:
        return "waiting for OpenCode agent"
    return f"messages={len(messages)} · waiting for assistant"
