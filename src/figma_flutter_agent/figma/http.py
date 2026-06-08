"""HTTP retry helpers for the Figma API client."""

from __future__ import annotations

import time
from email.utils import parsedate_to_datetime

import httpx

from figma_flutter_agent.errors import FigmaApiError
from figma_flutter_agent.figma.limits import (
    MAX_AUTO_RETRY_DELAY_SEC,
    UNIX_TIMESTAMP_THRESHOLD,
)


def format_transport_error(exc: httpx.TransportError) -> str:
    """One-line transport failure summary for logs and CLI errors."""
    name = type(exc).__name__
    detail = str(exc).strip()
    return f"{name} ({detail})" if detail else name


def transport_failure_message(method: str, path: str, exc: httpx.TransportError) -> str:
    """Human-readable Figma API transport error after retries are exhausted."""
    detail = format_transport_error(exc)
    return (
        f"Could not reach Figma API ({detail}) for {method} {path}. "
        "Check network or VPN, retry later, or use offline mode (--from-dump)."
    )


def parse_retry_after_seconds(raw: str) -> float | None:
    """Parse a ``Retry-After`` header value into seconds to wait."""
    value = raw.strip()
    if not value:
        return None
    try:
        numeric = float(value)
    except ValueError:
        numeric = None
    if numeric is not None:
        if numeric >= UNIX_TIMESTAMP_THRESHOLD:
            return max(numeric - time.time(), 0.0)
        return max(numeric, 0.0)
    try:
        retry_at = parsedate_to_datetime(value)
        return max(retry_at.timestamp() - time.time(), 0.0)
    except (TypeError, ValueError, OSError):
        return None


def retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            parsed = parse_retry_after_seconds(retry_after)
            if parsed is not None:
                return parsed
    return float(2**attempt)


def rate_limit_error(response: httpx.Response, delay_sec: float) -> FigmaApiError:
    """Build a descriptive rate-limit error with Figma response headers."""
    retry_after = response.headers.get("Retry-After", "")
    plan_tier = response.headers.get("X-Figma-Plan-Tier", "")
    limit_type = response.headers.get("X-Figma-Rate-Limit-Type", "")
    upgrade_link = response.headers.get("X-Figma-Upgrade-Link", "")
    hours = delay_sec / 3600.0
    message = (
        f"Figma rate limit exceeded (429). Retry-After={retry_after!r} "
        f"({delay_sec:.0f}s, {hours:.1f}h). "
        f"Automatic retry is capped at {MAX_AUTO_RETRY_DELAY_SEC:.0f}s."
    )
    if plan_tier or limit_type:
        message += f" Plan={plan_tier or 'unknown'}, limit={limit_type or 'unknown'}."
    if upgrade_link:
        message += f" Upgrade: {upgrade_link}"
    message += (
        " Wait for the bucket to refill or use a cached dump "
        "(scripts/regen-layout-from-dump.py) to avoid live API calls."
    )
    return FigmaApiError(message, status_code=429)
