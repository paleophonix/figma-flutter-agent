"""Grafana Loki push sink for Loguru."""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from figma_flutter_agent.config import Settings

_DEFAULT_SERVICE_LABEL = "figma-flutter-agent"
_PUSH_PATH_SUFFIX = "/loki/api/v1/push"
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_SENTINEL = object()


@dataclass(frozen=True)
class _PushPolicy:
    """HTTP retry policy for Loki push batches."""

    max_attempts: int
    timeout_sec: float
    retry_base_sec: float


@dataclass(frozen=True)
class _LogEntry:
    """One log line destined for Loki."""

    ts_ns: str
    line: str


def normalize_loki_push_url(url: str) -> str:
    """Normalize a Loki base or push URL to the v1 push endpoint.

    Args:
        url: Raw ``LOKI_URL`` value.

    Returns:
        Push endpoint URL, or an empty string when ``url`` is blank.
    """
    normalized = url.strip().rstrip("/")
    if not normalized:
        return ""
    if normalized.endswith(_PUSH_PATH_SUFFIX):
        return normalized
    return f"{normalized}{_PUSH_PATH_SUFFIX}"


def parse_loki_labels(raw: str) -> dict[str, str]:
    """Parse comma-separated ``key=value`` labels for Loki streams.

    Args:
        raw: ``LOKI_LABELS`` env value.

    Returns:
        Label map including the default ``service`` label.
    """
    labels = {"service": _DEFAULT_SERVICE_LABEL}
    for part in raw.split(","):
        token = part.strip()
        if not token or "=" not in token:
            continue
        key, value = token.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            labels[key] = value
    return labels


def loki_push_enabled(settings: Settings) -> bool:
    """Return whether remote Loki shipping is active."""
    if not settings.loki_enabled:
        return False
    return bool(normalize_loki_push_url(settings.loki_url))


def _push_policy(settings: Settings) -> _PushPolicy:
    return _PushPolicy(
        max_attempts=settings.loki_push_max_attempts,
        timeout_sec=settings.loki_push_timeout_sec,
        retry_base_sec=settings.loki_push_retry_base_sec,
    )


def _retry_delay(policy: _PushPolicy, attempt: int) -> float:
    return policy.retry_base_sec * (2 ** (attempt - 1))


def _format_log_line(record: dict[str, Any]) -> str:
    payload: dict[str, Any] = {
        "level": record["level"].name,
        "logger": f"{record['name']}:{record['function']}:{record['line']}",
        "message": str(record["message"]),
    }
    extra = {
        key: value
        for key, value in record["extra"].items()
        if key not in {"", None} and value not in ("", None)
    }
    if extra:
        payload["extra"] = extra
    return json.dumps(payload, ensure_ascii=False, default=str)


class _BearerAuth(httpx.Auth):
    """Attach a bearer token without relying on httpx auth helpers."""

    def __init__(self, token: str) -> None:
        self._token = token

    def auth_flow(self, request: httpx.Request) -> Any:
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


def _build_auth(settings: Settings) -> httpx.Auth | None:
    user = settings.loki_user.strip()
    token = settings.loki_api_key.get_secret_value().strip()
    if user and token:
        return httpx.BasicAuth(user, token)
    if token:
        return _BearerAuth(token)
    return None


def _safe_push_host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return url


class LokiSink:
    """Background batching sink that pushes Loguru records to Grafana Loki."""

    def __init__(self, settings: Settings) -> None:
        self._url = normalize_loki_push_url(settings.loki_url)
        self._labels = parse_loki_labels(settings.loki_labels)
        self._policy = _push_policy(settings)
        self._batch_size = settings.loki_batch_size
        self._flush_interval_sec = settings.loki_flush_interval_sec
        self._auth = _build_auth(settings)
        self._queue: queue.SimpleQueue[_LogEntry | object] = queue.SimpleQueue()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="loki-push",
            daemon=True,
        )
        self._thread.start()

    @property
    def push_host(self) -> str:
        """Return the Loki host for diagnostics (no credentials)."""
        return _safe_push_host(self._url)

    def write(self, message: Any) -> None:
        """Loguru sink entrypoint."""
        record = message.record
        self._queue.put(
            _LogEntry(
                ts_ns=str(int(record["time"].timestamp() * 1_000_000_000)),
                line=_format_log_line(record),
            )
        )

    def close(self) -> None:
        """Stop the background pusher and flush pending entries."""
        self._stop.set()
        self._queue.put(_SENTINEL)
        self._thread.join(timeout=min(self._flush_interval_sec + 1.0, 3.0))

    def _run(self) -> None:
        batch: list[_LogEntry] = []
        next_flush = time.monotonic() + self._flush_interval_sec
        while True:
            timeout = max(0.0, next_flush - time.monotonic())
            try:
                item = self._queue.get(timeout=timeout)
            except queue.Empty:
                item = None

            if item is _SENTINEL:
                if batch:
                    self._push_batch(batch)
                return

            if isinstance(item, _LogEntry):
                batch.append(item)
                if len(batch) >= self._batch_size:
                    self._push_batch(batch)
                    batch = []
                    next_flush = time.monotonic() + self._flush_interval_sec
                    continue

            if batch and time.monotonic() >= next_flush:
                self._push_batch(batch)
                batch = []
                next_flush = time.monotonic() + self._flush_interval_sec

    def _push_batch(self, batch: list[_LogEntry]) -> None:
        payload = {
            "streams": [
                {
                    "stream": self._labels,
                    "values": [[entry.ts_ns, entry.line] for entry in batch],
                }
            ]
        }
        self._send_payload(payload, batch_size=len(batch))

    def _send_payload(self, payload: dict[str, Any], *, batch_size: int) -> None:
        policy = self._policy
        last_error: str | None = None
        for attempt in range(1, policy.max_attempts + 1):
            try:
                response = httpx.post(
                    self._url,
                    json=payload,
                    auth=self._auth,
                    timeout=policy.timeout_sec,
                )
                if response.status_code < 400:
                    return
                last_error = f"HTTP {response.status_code}"
                if response.status_code in _RETRYABLE_STATUS and attempt < policy.max_attempts:
                    time.sleep(_retry_delay(policy, attempt))
                    continue
                logger.warning(
                    "Loki push HTTP {} for host={} (batch_size={})",
                    response.status_code,
                    self.push_host,
                    batch_size,
                )
                return
            except httpx.TimeoutException:
                last_error = f"timeout after {policy.timeout_sec}s"
                if attempt < policy.max_attempts:
                    time.sleep(_retry_delay(policy, attempt))
                    continue
            except httpx.TransportError as exc:
                last_error = str(exc)
                if attempt < policy.max_attempts:
                    time.sleep(_retry_delay(policy, attempt))
                    continue
            except Exception as exc:
                logger.warning(
                    "Loki push failed for host={} (batch_size={}): {}",
                    self.push_host,
                    batch_size,
                    exc,
                )
                return

        logger.warning(
            "Loki push gave up after {} attempts for host={} (batch_size={}): {}",
            policy.max_attempts,
            self.push_host,
            batch_size,
            last_error or "unknown error",
        )


_active_sink: LokiSink | None = None


def attach_loki_sink(*, settings: Settings, level: str) -> LokiSink | None:
    """Attach a Loki sink to Loguru when ``LOKI_URL`` is configured.

    Args:
        settings: Application settings with Loki env vars.
        level: Minimum log level for the sink.

    Returns:
        Active sink instance, or ``None`` when Loki is disabled.
    """
    global _active_sink
    shutdown_loki_sink()
    if not loki_push_enabled(settings):
        return None
    sink = LokiSink(settings)
    logger.add(
        sink.write,
        level=level,
        format="{message}",
        enqueue=True,
        catch=True,
    )
    _active_sink = sink
    return sink


def shutdown_loki_sink() -> None:
    """Stop and detach the active Loki sink, if any."""
    global _active_sink
    if _active_sink is None:
        return
    _active_sink.close()
    _active_sink = None


def active_loki_sink() -> LokiSink | None:
    """Return the active Loki sink for diagnostics."""
    return _active_sink
