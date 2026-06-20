"""PostHog ``$ai_generation`` capture for figma-flutter LLM calls."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.llm.capabilities import LlmProvider
from figma_flutter_agent.observability.posthog_transport import (
    CaptureRequest,
    capture_policy_from,
    send_capture,
)

_ANALYTICS_TEXT_LIMIT = 12_000


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


@dataclass(frozen=True)
class _LlmCaptureJob:
    """Snapshot for a background PostHog LLM ingest request."""

    api_key: str
    host: str
    trace_id: str
    span_name: str
    span_id: str | None
    parent_span_id: str | None
    provider: LlmProvider
    model: str
    latency_sec: float
    system_prompt: str
    user_prompt: str
    output_text: str | None
    is_error: bool
    error_message: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_cost_usd: float | None
    input_cost_usd: float | None
    output_cost_usd: float | None
    policy: Any


def _build_llm_properties(job: _LlmCaptureJob) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "$ai_trace_id": job.trace_id,
        "$ai_span_name": job.span_name,
        "$ai_model": job.model,
        "$ai_provider": job.provider,
        "$ai_input": _sanitize_messages(job.system_prompt, job.user_prompt),
        "$ai_latency": job.latency_sec,
        "$ai_is_error": job.is_error,
    }
    if job.span_id is not None:
        properties["$ai_span_id"] = job.span_id
    if job.parent_span_id is not None:
        properties["$ai_parent_id"] = job.parent_span_id
    if job.error_message:
        properties["$ai_error"] = _truncate_text(job.error_message, limit=4000)
    if job.output_text is not None:
        properties["$ai_output_choices"] = [
            {"role": "assistant", "content": _truncate_text(job.output_text)}
        ]
    if job.input_tokens is not None:
        properties["$ai_input_tokens"] = job.input_tokens
    if job.output_tokens is not None:
        properties["$ai_output_tokens"] = job.output_tokens
    if job.input_cost_usd is not None:
        properties["$ai_input_cost_usd"] = job.input_cost_usd
    if job.output_cost_usd is not None:
        properties["$ai_output_cost_usd"] = job.output_cost_usd
    if job.total_cost_usd is not None:
        properties["$ai_total_cost_usd"] = job.total_cost_usd
    return properties


def _send_llm_capture(job: _LlmCaptureJob) -> None:
    request = CaptureRequest(
        api_key=job.api_key,
        host=job.host,
        event="$ai_generation",
        distinct_id=job.trace_id,
        properties=_build_llm_properties(job),
        policy=job.policy,
        log_label=f"trace_id={job.trace_id} span={job.span_name}",
    )
    send_capture(request)


def capture_ai_trace(
    *,
    settings: Settings,
    trace_id: str,
    span_name: str,
    root_span_id: str,
    is_error: bool = False,
    latency_sec: float | None = None,
    extra_properties: dict[str, Any] | None = None,
) -> None:
    """Queue one PostHog ``$ai_trace`` root event for a pipeline run (never raises).

    Args:
        settings: Application settings with PostHog flags and API key.
        trace_id: Pipeline run id shared by all child generations.
        span_name: Human-readable trace label (for example ``repair.sign_up``).
        root_span_id: Stable parent span id referenced by child ``$ai_parent_id``.
        is_error: Whether the pipeline ended in error.
        latency_sec: Optional end-to-end pipeline latency in seconds.
        extra_properties: Optional custom properties (feature, project, command).
    """
    api_key = settings.posthog_api_key.get_secret_value()
    if not api_key:
        return

    properties: dict[str, Any] = {
        "$ai_trace_id": trace_id,
        "$ai_span_id": root_span_id,
        "$ai_span_name": span_name,
        "$ai_is_error": is_error,
    }
    if latency_sec is not None:
        properties["$ai_latency"] = latency_sec
    if extra_properties:
        properties.update(extra_properties)

    request = CaptureRequest(
        api_key=api_key,
        host=settings.posthog_host,
        event="$ai_trace",
        distinct_id=trace_id,
        properties=properties,
        policy=capture_policy_from(settings),
        log_label=f"trace_id={trace_id} span={span_name}",
    )
    threading.Thread(
        target=send_capture,
        args=(request,),
        name=f"posthog-trace-{span_name}",
        daemon=True,
    ).start()


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
    total_cost_usd: float | None = None,
    input_cost_usd: float | None = None,
    output_cost_usd: float | None = None,
    parent_span_id: str | None = None,
    span_id: str | None = None,
) -> None:
    """Queue a PostHog ``$ai_generation`` event (never raises, does not block the caller).

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
        total_cost_usd: Total provider-reported cost in USD (OpenRouter ``usage.cost``).
        input_cost_usd: Input-token cost in USD when reported by the provider.
        output_cost_usd: Output-token cost in USD when reported by the provider.
        parent_span_id: Parent span id (pipeline root) for trace tree grouping.
        span_id: Unique span id for this generation; allocated when omitted.
    """
    api_key = settings.posthog_api_key.get_secret_value()
    if not api_key:
        return

    from figma_flutter_agent.observability.llm_trace import (
        current_trace_root_span_id,
        next_generation_span_id,
    )

    resolved_parent = parent_span_id or current_trace_root_span_id()
    resolved_span_id = span_id or next_generation_span_id(
        trace_id=trace_id,
        span_name=span_name,
    )

    job = _LlmCaptureJob(
        api_key=api_key,
        host=settings.posthog_host,
        trace_id=trace_id,
        span_name=span_name,
        span_id=resolved_span_id,
        parent_span_id=resolved_parent,
        provider=provider,
        model=model,
        latency_sec=latency_sec,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_text=output_text,
        is_error=is_error,
        error_message=error_message,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost_usd=total_cost_usd,
        input_cost_usd=input_cost_usd,
        output_cost_usd=output_cost_usd,
        policy=capture_policy_from(settings),
    )
    threading.Thread(
        target=_send_llm_capture,
        args=(job,),
        name=f"posthog-llm-{span_name}",
        daemon=True,
    ).start()
