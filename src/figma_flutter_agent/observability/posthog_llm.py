"""PostHog ``$ai_generation`` capture for figma-flutter LLM calls."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.llm.capabilities import LlmProvider

_ANALYTICS_TEXT_LIMIT = 12_000
_CAPTURE_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


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


@dataclass(frozen=True)
class _CapturePolicy:
    """Retry and timeout policy loaded from ``Settings``."""

    max_attempts: int
    timeout_sec: float
    retry_base_sec: float


@dataclass(frozen=True)
class _CaptureJob:
    """Snapshot for a background PostHog ingest request."""

    api_key: str
    host: str
    trace_id: str
    span_name: str
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
    policy: _CapturePolicy


def _capture_policy(settings: Settings) -> _CapturePolicy:
    return _CapturePolicy(
        max_attempts=settings.posthog_capture_max_attempts,
        timeout_sec=settings.posthog_capture_timeout_sec,
        retry_base_sec=settings.posthog_capture_retry_base_sec,
    )


def _build_capture_payload(job: _CaptureJob) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "$ai_trace_id": job.trace_id,
        "$ai_span_name": job.span_name,
        "$ai_model": job.model,
        "$ai_provider": job.provider,
        "$ai_input": _sanitize_messages(job.system_prompt, job.user_prompt),
        "$ai_latency": job.latency_sec,
        "$ai_is_error": job.is_error,
    }
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
    return {
        "api_key": job.api_key,
        "event": "$ai_generation",
        "distinct_id": job.trace_id,
        "properties": properties,
    }


def _capture_retry_delay(policy: _CapturePolicy, attempt: int) -> float:
    return policy.retry_base_sec * (2 ** (attempt - 1))


def _post_capture(job: _CaptureJob) -> httpx.Response:
    return httpx.post(
        _capture_url(job.host),
        json=_build_capture_payload(job),
        timeout=job.policy.timeout_sec,
    )


def _send_capture(job: _CaptureJob) -> None:
    """POST one capture payload with retries (runs off the LLM hot path)."""
    policy = job.policy
    last_error: str | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = _post_capture(job)
            if response.status_code < 400:
                if attempt > 1:
                    logger.info(
                        "PostHog LLM capture succeeded on attempt {}/{} for trace_id={} span={}",
                        attempt,
                        policy.max_attempts,
                        job.trace_id,
                        job.span_name,
                    )
                return
            last_error = f"HTTP {response.status_code}"
            if response.status_code in _CAPTURE_RETRYABLE_STATUS and attempt < policy.max_attempts:
                delay = _capture_retry_delay(policy, attempt)
                logger.warning(
                    "PostHog LLM capture HTTP {} for trace_id={} span={}; "
                    "retrying in {:.1f}s ({}/{})",
                    response.status_code,
                    job.trace_id,
                    job.span_name,
                    delay,
                    attempt,
                    policy.max_attempts,
                )
                time.sleep(delay)
                continue
            logger.warning(
                "PostHog LLM capture HTTP {} for trace_id={} span={}",
                response.status_code,
                job.trace_id,
                job.span_name,
            )
            return
        except httpx.TimeoutException:
            last_error = f"timeout after {policy.timeout_sec}s"
            if attempt < policy.max_attempts:
                delay = _capture_retry_delay(policy, attempt)
                logger.warning(
                    "PostHog LLM capture timed out for trace_id={} span={}; "
                    "retrying in {:.1f}s ({}/{})",
                    job.trace_id,
                    job.span_name,
                    delay,
                    attempt,
                    policy.max_attempts,
                )
                time.sleep(delay)
                continue
        except httpx.TransportError as exc:
            last_error = str(exc)
            if attempt < policy.max_attempts:
                delay = _capture_retry_delay(policy, attempt)
                logger.warning(
                    "PostHog LLM capture transport error for trace_id={} span={}: {}; "
                    "retrying in {:.1f}s ({}/{})",
                    job.trace_id,
                    job.span_name,
                    exc,
                    delay,
                    attempt,
                    policy.max_attempts,
                )
                time.sleep(delay)
                continue
        except Exception as exc:
            logger.warning(
                "PostHog LLM capture failed for trace_id={} span={}: {}",
                job.trace_id,
                job.span_name,
                exc,
            )
            return

    logger.warning(
        "PostHog LLM capture gave up after {} attempts for trace_id={} span={}: {}",
        policy.max_attempts,
        job.trace_id,
        job.span_name,
        last_error or "unknown error",
    )


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
    """
    api_key = settings.posthog_api_key.get_secret_value()
    if not api_key:
        return

    job = _CaptureJob(
        api_key=api_key,
        host=settings.posthog_host,
        trace_id=trace_id,
        span_name=span_name,
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
        policy=_capture_policy(settings),
    )
    threading.Thread(
        target=_send_capture,
        args=(job,),
        name=f"posthog-llm-{span_name}",
        daemon=True,
    ).start()
