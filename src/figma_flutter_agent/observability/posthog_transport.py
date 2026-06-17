"""Shared PostHog HTTP capture transport."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from loguru import logger
from pydantic import SecretStr

_CAPTURE_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class PostHogCaptureSettings(Protocol):
    """Settings surface required for PostHog background capture."""

    posthog_api_key: SecretStr
    posthog_host: str
    posthog_capture_max_attempts: int
    posthog_capture_timeout_sec: float
    posthog_capture_retry_base_sec: float


@dataclass(frozen=True)
class CapturePolicy:
    """Retry and timeout policy for PostHog ingest."""

    max_attempts: int
    timeout_sec: float
    retry_base_sec: float


@dataclass(frozen=True)
class CaptureRequest:
    """One PostHog capture ingest request."""

    api_key: str
    host: str
    event: str
    distinct_id: str
    properties: dict[str, Any]
    policy: CapturePolicy
    log_label: str


def capture_policy_from(settings: PostHogCaptureSettings) -> CapturePolicy:
    """Build capture policy from application settings."""
    return CapturePolicy(
        max_attempts=settings.posthog_capture_max_attempts,
        timeout_sec=settings.posthog_capture_timeout_sec,
        retry_base_sec=settings.posthog_capture_retry_base_sec,
    )


def capture_url(host: str) -> str:
    """Normalize PostHog ingest URL."""
    normalized = host.strip().rstrip("/") or "https://us.i.posthog.com"
    if normalized.endswith("/capture"):
        return f"{normalized}/"
    return f"{normalized}/capture/"


def build_capture_body(request: CaptureRequest) -> dict[str, Any]:
    """Build PostHog ``/capture`` JSON body."""
    return {
        "api_key": request.api_key,
        "event": request.event,
        "distinct_id": request.distinct_id,
        "properties": request.properties,
    }


def _capture_retry_delay(policy: CapturePolicy, attempt: int) -> float:
    return policy.retry_base_sec * (2 ** (attempt - 1))


def _post_capture(request: CaptureRequest) -> httpx.Response:
    return httpx.post(
        capture_url(request.host),
        json=build_capture_body(request),
        timeout=request.policy.timeout_sec,
    )


def send_capture(request: CaptureRequest) -> None:
    """POST one capture payload with retries (blocking; run off the hot path)."""
    policy = request.policy
    last_error: str | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = _post_capture(request)
            if response.status_code < 400:
                if attempt > 1:
                    logger.info(
                        "PostHog capture succeeded on attempt {}/{} for event={} {}",
                        attempt,
                        policy.max_attempts,
                        request.event,
                        request.log_label,
                    )
                return
            last_error = f"HTTP {response.status_code}"
            if response.status_code in _CAPTURE_RETRYABLE_STATUS and attempt < policy.max_attempts:
                delay = _capture_retry_delay(policy, attempt)
                logger.warning(
                    "PostHog capture HTTP {} for event={} {}; retrying in {:.1f}s ({}/{})",
                    response.status_code,
                    request.event,
                    request.log_label,
                    delay,
                    attempt,
                    policy.max_attempts,
                )
                time.sleep(delay)
                continue
            logger.warning(
                "PostHog capture HTTP {} for event={} {}",
                response.status_code,
                request.event,
                request.log_label,
            )
            return
        except httpx.TimeoutException:
            last_error = f"timeout after {policy.timeout_sec}s"
            if attempt < policy.max_attempts:
                delay = _capture_retry_delay(policy, attempt)
                logger.warning(
                    "PostHog capture timed out for event={} {}; retrying in {:.1f}s ({}/{})",
                    request.event,
                    request.log_label,
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
                    "PostHog capture transport error for event={} {}: {}; retrying in {:.1f}s ({}/{})",
                    request.event,
                    request.log_label,
                    exc,
                    delay,
                    attempt,
                    policy.max_attempts,
                )
                time.sleep(delay)
                continue
        except Exception as exc:
            logger.warning(
                "PostHog capture failed for event={} {}: {}",
                request.event,
                request.log_label,
                exc,
            )
            return

    logger.warning(
        "PostHog capture gave up after {} attempts for event={} {}: {}",
        policy.max_attempts,
        request.event,
        request.log_label,
        last_error or "unknown error",
    )


def enqueue_capture(request: CaptureRequest) -> None:
    """Queue a background PostHog capture (never raises)."""
    threading.Thread(
        target=send_capture,
        args=(request,),
        name=f"posthog-{request.event}",
        daemon=True,
    ).start()
