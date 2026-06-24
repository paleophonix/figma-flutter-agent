"""Prometheus collectors and helpers for ops/SLO metrics."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# --- Control panel (scraped from FastAPI /metrics) ---

CONTROL_PANEL_READY = Gauge(
    "control_panel_ready",
    "Component readiness (1=ok).",
    ["component"],
)

CONTROL_PANEL_JOBS_SNAPSHOT = Gauge(
    "control_panel_jobs_snapshot",
    "Generation jobs grouped by status and origin (DB snapshot).",
    ["status", "origin"],
)

CONTROL_PANEL_REPAIR_JOBS_SNAPSHOT = Gauge(
    "control_panel_repair_jobs_snapshot",
    "Repair jobs grouped by status (DB snapshot).",
    ["status"],
)

CONTROL_PANEL_HTTP_REQUESTS = Counter(
    "control_panel_http_requests_total",
    "HTTP requests to the control panel API.",
    ["method", "route", "status"],
)

CONTROL_PANEL_RATE_LIMIT_HITS = Counter(
    "control_panel_rate_limit_hits_total",
    "API rate limit rejections.",
    ["scope"],
)

CONTROL_PANEL_WEBHOOK_EVENTS = Counter(
    "control_panel_webhook_events_total",
    "Webhook events processed.",
    ["provider", "object_kind", "outcome"],
)

# --- ARQ worker ---

ARQ_JOBS_TOTAL = Counter(
    "arq_jobs_total",
    "ARQ task terminal outcomes.",
    ["task", "outcome"],
)

ARQ_JOB_DURATION = Histogram(
    "arq_job_duration_seconds",
    "ARQ task wall time.",
    ["task"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600),
)

ARQ_JOBS_IN_FLIGHT = Gauge(
    "arq_jobs_in_flight",
    "ARQ tasks currently executing.",
    ["task"],
)

# --- Generation pipeline ---

PIPELINE_STAGE_DURATION = Histogram(
    "pipeline_stage_duration_seconds",
    "Pipeline stage wall time.",
    ["stage", "outcome"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600),
)

PIPELINE_RUNS_TOTAL = Counter(
    "pipeline_runs_total",
    "Generation pipeline runs from the control panel worker.",
    ["outcome"],
)

# --- Figma API ---

FIGMA_API_REQUESTS = Counter(
    "figma_api_requests_total",
    "Figma REST API requests.",
    ["endpoint", "status_class"],
)

FIGMA_API_REQUEST_DURATION = Histogram(
    "figma_api_request_duration_seconds",
    "Figma REST API request latency.",
    ["endpoint"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

FIGMA_API_RATE_LIMITED = Counter(
    "figma_api_rate_limited_total",
    "Figma API rate-limit responses (HTTP 429).",
)

# --- LLM (ops counters; PostHog keeps token detail) ---

LLM_REQUESTS = Counter(
    "llm_requests_total",
    "LLM generation requests.",
    ["span_name", "outcome"],
)

LLM_REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "LLM generation latency.",
    ["span_name"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600),
)

# --- Repair pipeline ---

REPAIR_STAGE_DURATION = Histogram(
    "repair_stage_duration_seconds",
    "Repair pipeline stage wall time.",
    ["stage", "outcome"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600),
)

REPAIR_QUEUE_DEPTH = Gauge(
    "repair_queue_depth",
    "Queued repair jobs waiting for the serial worker slot.",
)

REPAIR_GATES_TOTAL = Counter(
    "repair_gates_total",
    "Repair quality gate outcomes.",
    ["gate", "outcome"],
)

_JOBS_SNAPSHOT_KEYS: set[tuple[str, str]] = set()
_REPAIR_SNAPSHOT_KEYS: set[str] = set()

FORBIDDEN_LABEL_NAMES = frozenset(
    {
        "job_id",
        "figma_url",
        "feature_slug",
        "principal",
        "node_id",
        "model",
    }
)


def render_metrics() -> bytes:
    """Return Prometheus text exposition for the default registry."""
    return generate_latest()


def metrics_content_type() -> str:
    """Return the Prometheus exposition content type."""
    return CONTENT_TYPE_LATEST


def set_component_ready(component: str, ok: bool) -> None:
    """Set readiness gauge for one infrastructure component."""
    CONTROL_PANEL_READY.labels(component=component).set(1 if ok else 0)


def refresh_jobs_snapshot(counts: dict[tuple[str, str], int]) -> None:
    """Update generation job DB snapshot gauges."""
    global _JOBS_SNAPSHOT_KEYS
    for key in _JOBS_SNAPSHOT_KEYS - counts.keys():
        status, origin = key
        CONTROL_PANEL_JOBS_SNAPSHOT.labels(status=status, origin=origin).set(0)
    for (status, origin), count in counts.items():
        CONTROL_PANEL_JOBS_SNAPSHOT.labels(status=status, origin=origin).set(count)
    _JOBS_SNAPSHOT_KEYS = set(counts.keys())


def refresh_repair_jobs_snapshot(counts: dict[str, int]) -> None:
    """Update repair job DB snapshot gauges."""
    global _REPAIR_SNAPSHOT_KEYS
    for status in _REPAIR_SNAPSHOT_KEYS - counts.keys():
        CONTROL_PANEL_REPAIR_JOBS_SNAPSHOT.labels(status=status).set(0)
    for status, count in counts.items():
        CONTROL_PANEL_REPAIR_JOBS_SNAPSHOT.labels(status=status).set(count)
    _REPAIR_SNAPSHOT_KEYS = set(counts.keys())


def observe_pipeline_stage(stage: str, duration_sec: float, *, outcome: str) -> None:
    """Record one pipeline stage duration."""
    PIPELINE_STAGE_DURATION.labels(stage=stage, outcome=outcome).observe(duration_sec)


def inc_pipeline_run(outcome: str) -> None:
    """Increment pipeline run counter."""
    PIPELINE_RUNS_TOTAL.labels(outcome=outcome).inc()


def inc_arq_job(task: str, outcome: str) -> None:
    """Increment ARQ terminal outcome counter."""
    ARQ_JOBS_TOTAL.labels(task=task, outcome=outcome).inc()


def observe_arq_job_duration(task: str, duration_sec: float) -> None:
    """Record ARQ task wall time."""
    ARQ_JOB_DURATION.labels(task=task).observe(duration_sec)


@contextmanager
def track_arq_job(task: str) -> Iterator[None]:
    """Track in-flight gauge, duration, and terminal outcome for one ARQ handler."""
    ARQ_JOBS_IN_FLIGHT.labels(task=task).inc()
    started = time.perf_counter()
    outcome = "success"
    try:
        yield
    except Exception:
        outcome = "failed"
        raise
    finally:
        ARQ_JOBS_IN_FLIGHT.labels(task=task).dec()
        observe_arq_job_duration(task, time.perf_counter() - started)
        inc_arq_job(task, outcome)


def _figma_endpoint(path: str) -> str:
    """Normalize Figma path to a low-cardinality endpoint label."""
    parts = [part for part in path.strip("/").split("/") if part]
    if not parts:
        return "root"
    if parts[0] == "v1" and len(parts) > 1:
        return f"/v1/{parts[1]}"
    return f"/{parts[0]}"


def _http_status_class(status_code: int) -> str:
    if status_code == 429:
        return "429"
    if 200 <= status_code < 300:
        return "2xx"
    if 400 <= status_code < 500:
        return "4xx"
    if 500 <= status_code < 600:
        return "5xx"
    return "other"


def observe_figma_request(path: str, status_code: int, duration_sec: float) -> None:
    """Record one Figma API request."""
    endpoint = _figma_endpoint(path)
    status_class = _http_status_class(status_code)
    FIGMA_API_REQUESTS.labels(endpoint=endpoint, status_class=status_class).inc()
    FIGMA_API_REQUEST_DURATION.labels(endpoint=endpoint).observe(duration_sec)
    if status_code == 429:
        FIGMA_API_RATE_LIMITED.inc()


def record_llm_request(
    span_name: str,
    *,
    latency_sec: float,
    is_error: bool,
) -> None:
    """Record LLM ops metrics alongside PostHog capture."""
    if not span_name:
        return
    outcome = "error" if is_error else "success"
    LLM_REQUESTS.labels(span_name=span_name, outcome=outcome).inc()
    LLM_REQUEST_DURATION.labels(span_name=span_name).observe(latency_sec)


def observe_repair_stage(stage: str, duration_sec: float, *, outcome: str) -> None:
    """Record one repair pipeline stage duration."""
    REPAIR_STAGE_DURATION.labels(stage=stage, outcome=outcome).observe(duration_sec)


@contextmanager
def track_repair_stage(stage: str) -> Iterator[None]:
    """Time one repair stage and record success/error outcome."""
    started = time.perf_counter()
    outcome = "success"
    try:
        yield
    except Exception:
        outcome = "error"
        raise
    finally:
        observe_repair_stage(stage, time.perf_counter() - started, outcome=outcome)


def set_repair_queue_depth(depth: int) -> None:
    """Set queued repair job depth gauge."""
    REPAIR_QUEUE_DEPTH.set(max(depth, 0))


def inc_repair_gate(gate: str, outcome: str) -> None:
    """Increment repair gate pass/fail counter."""
    REPAIR_GATES_TOTAL.labels(gate=gate, outcome=outcome).inc()


def inc_rate_limit(scope: str) -> None:
    """Increment API rate-limit rejection counter."""
    CONTROL_PANEL_RATE_LIMIT_HITS.labels(scope=scope).inc()


def inc_webhook_event(provider: str, object_kind: str, outcome: str) -> None:
    """Increment webhook processing counter."""
    CONTROL_PANEL_WEBHOOK_EVENTS.labels(
        provider=provider,
        object_kind=object_kind,
        outcome=outcome,
    ).inc()


def inc_http_request(method: str, route: str, status: int) -> None:
    """Increment control panel HTTP request counter."""
    CONTROL_PANEL_HTTP_REQUESTS.labels(
        method=method,
        route=route,
        status=str(status),
    ).inc()


def assert_low_cardinality_labels(metric: Any) -> None:
    """Raise when a collector uses forbidden high-cardinality label names."""
    labelnames = getattr(metric, "_labelnames", ())
    forbidden = FORBIDDEN_LABEL_NAMES.intersection(labelnames)
    if forbidden:
        raise ValueError(f"Forbidden metric labels: {sorted(forbidden)}")
