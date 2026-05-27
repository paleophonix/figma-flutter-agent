"""PostHog ``$ai_generation`` capture for figma-flutter LLM calls."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.llm.capabilities import LlmProvider

_ANALYTICS_TEXT_LIMIT = 12_000
_CAPTURE_TIMEOUT_SEC = 5.0


def _truncate_text(text: str, *, limit: int = _ANALYTICS_TEXT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}... [truncated {omitted} chars]"


def _sanitize_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _truncate_text(system_prompt)},
        {"role": "user", "content": _truncate_text(user_prompt)},
    ]


def _capture_url(host: str) -> str:
    normalized = host.strip().rstrip("/") or "https://us.i.posthog.com"
    if normalized.endswith("/capture"):
        return f"{normalized}/"
    return f"{normalized}/capture/"


def capture_ai_generation(
    *,
    settings: Settings,
    trace_id: str,
    span_name: str,
    provider: LlmProvider,
    model: str,
    latency_sec: float,
    system_prompt: str,
    user_prompt: str,
    output_text: str | None,
    is_error: bool,
    error_message: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    """Send a PostHog ``$ai_generation`` event (never raises).

    Args:
        settings: Application settings with PostHog flags and API key.
        trace_id: Pipeline run id used as ``$ai_trace_id`` (one trace per run).
        span_name: Span label (generate, repair, refine) as ``$ai_span_name``.
        provider: Active LLM provider id.
        model: Model id sent to the provider.
        latency_sec: End-to-end request latency in seconds.
        system_prompt: System prompt text (truncated for analytics).
        user_prompt: User prompt text (truncated for analytics).
        output_text: Model output text when the call succeeded.
        is_error: Whether the provider call failed.
        error_message: Error summary when ``is_error`` is true.
        input_tokens: Prompt tokens when reported by the provider.
        output_tokens: Completion tokens when reported by the provider.
    """
    api_key = settings.posthog_api_key.get_secret_value()
    if not api_key:
        return

    properties: dict[str, Any] = {
        "$ai_trace_id": trace_id,
        "$ai_span_name": span_name,
        "$ai_model": model,
        "$ai_provider": provider,
        "$ai_input": _sanitize_messages(system_prompt, user_prompt),
        "$ai_latency": latency_sec,
        "$ai_is_error": is_error,
    }
    if error_message:
        properties["$ai_error"] = _truncate_text(error_message, limit=4000)
    if output_text is not None:
        properties["$ai_output_choices"] = [
            {"role": "assistant", "content": _truncate_text(output_text)}
        ]
    if input_tokens is not None:
        properties["$ai_input_tokens"] = input_tokens
    if output_tokens is not None:
        properties["$ai_output_tokens"] = output_tokens

    payload = {
        "api_key": api_key,
        "event": "$ai_generation",
        "distinct_id": trace_id,
        "properties": properties,
    }

    try:
        response = httpx.post(
            _capture_url(settings.posthog_host),
            json=payload,
            timeout=_CAPTURE_TIMEOUT_SEC,
        )
        if response.status_code >= 400:
            logger.warning(
                "PostHog LLM capture failed with status {} for trace_id={}",
                response.status_code,
                trace_id,
            )
    except Exception:
        logger.exception("PostHog LLM capture request failed for trace_id={}", trace_id)
