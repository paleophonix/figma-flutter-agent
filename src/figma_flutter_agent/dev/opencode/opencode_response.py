"""Helpers for interpreting OpenCode session message responses."""

from __future__ import annotations

from typing import Any

_AGENT_SUMMARY_MAX_CHARS = 6_000


def extract_opencode_token_usage(response: dict[str, Any] | None) -> tuple[int | None, int | None]:
    """Return input/output token counts from an OpenCode prompt response."""
    if not isinstance(response, dict):
        return None, None
    info = response.get("info")
    if not isinstance(info, dict):
        return None, None
    tokens = info.get("tokens")
    if not isinstance(tokens, dict):
        return None, None
    raw_in = tokens.get("input")
    raw_out = tokens.get("output")
    tokens_in = int(raw_in) if isinstance(raw_in, (int, float)) else None
    tokens_out = int(raw_out) if isinstance(raw_out, (int, float)) else None
    return tokens_in, tokens_out


def opencode_provider_reached(response: dict[str, Any] | None) -> bool:
    """Return whether OpenCode completed an LLM round-trip (tokens or assistant text)."""
    if extract_opencode_prompt_error(response) is not None:
        return False
    tokens_in, tokens_out = extract_opencode_token_usage(response)
    if (tokens_in or 0) > 0 or (tokens_out or 0) > 0:
        return True
    return bool(extract_opencode_assistant_text(response).strip())


def extract_opencode_prompt_error(response: dict[str, Any] | None) -> str | None:
    """Return a provider/agent error message from an OpenCode prompt response.

    Args:
        response: Payload returned by ``OpenCodeClient.prompt_message``.

    Returns:
        Human-readable error text when the assistant message failed, else ``None``.
    """
    if not isinstance(response, dict):
        return None
    info = response.get("info")
    if not isinstance(info, dict):
        return None
    error = info.get("error")
    if not isinstance(error, dict):
        return None
    data = error.get("data")
    if isinstance(data, dict):
        message = data.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    name = error.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def extract_opencode_assistant_text(response: dict[str, Any] | None) -> str:
    """Concatenate assistant text parts from an OpenCode prompt response.

    Args:
        response: Payload returned by ``OpenCodeClient.prompt_message``.

    Returns:
        Combined assistant-visible text (may be empty).
    """
    if not isinstance(response, dict):
        return ""
    parts = response.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("type") != "text":
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return "\n\n".join(chunks)


def detect_repair_incomplete(
    response: dict[str, Any] | None,
    assistant_text: str,
) -> bool:
    """Return whether repair stopped before completing compiler edits."""
    if isinstance(response, dict):
        info = response.get("info")
        if isinstance(info, dict):
            finish = str(info.get("finishReason") or info.get("finish_reason") or "").lower()
            if finish in {"max_steps", "max_steps_reached", "tool_calls", "length"}:
                return True
            step_count = info.get("steps")
            max_steps = info.get("maxSteps") or info.get("max_steps")
            if (
                isinstance(step_count, (int, float))
                and isinstance(max_steps, (int, float))
                and max_steps > 0
                and step_count >= max_steps
            ):
                return True
    return detect_repair_steps_exhausted(assistant_text)


def detect_repair_steps_exhausted(assistant_text: str) -> bool:
    """Return whether the repair agent stopped due to OpenCode step budget.

    Args:
        assistant_text: Combined assistant message text from the repair session.

    Returns:
        True when the response indicates tool/step budget exhaustion before edits.
    """
    lowered = assistant_text.lower()
    if "maximum steps reached" in lowered:
        return True
    if "what was not completed" in lowered and (
        "remaining tasks" in lowered or "recommended next steps" in lowered
    ):
        return True
    return "remaining tasks:" in lowered and "next steps:" in lowered


def truncate_agent_summary(text: str, *, max_chars: int = _AGENT_SUMMARY_MAX_CHARS) -> str:
    """Bound repair continuation summaries for prompt injection."""
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars] + "\n\n[truncated]"
