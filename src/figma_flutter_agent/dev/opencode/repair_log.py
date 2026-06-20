"""Structured Loguru context for the OpenCode repair / wizard debug pipeline."""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from contextvars import ContextVar
from typing import Any

from loguru import logger

from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.observability.loki_sink import LOKI_APP_DEBUG, LOKI_TEAM_DEFAULT
from figma_flutter_agent.observability.llm_trace import (
    bind_pipeline_observability,
    clear_pipeline_observability,
)
from figma_flutter_agent.observability.posthog_llm import capture_ai_trace

_repair_log: ContextVar[Any] = ContextVar("repair_log", default=None)


def repair_logger() -> Any:
    """Return the bound repair logger or the global Loguru logger."""
    bound = _repair_log.get()
    return bound if bound is not None else logger


@contextmanager
def bind_repair_observability(
    *,
    run_id: str,
    feature: str,
    project: str,
    command: str,
    settings: Settings,
) -> Iterator[Any]:
    """Bind repair run context for Loki / PostHog correlation.

    Args:
        run_id: Trace or pipeline correlation id.
        feature: Screen feature slug.
        project: Flutter project label under ``.debug/<project>/``.
        command: CLI entry (for example ``wizard_debug``).
        settings: Loaded agent settings.

    Yields:
        Bound Loguru logger with repair fields in ``extra``.
    """
    root_span_id = bind_pipeline_observability(run_id=run_id, settings=settings)
    trace_cfg = settings.agent.debug_pipeline.trace
    if trace_cfg.posthog and settings.posthog_api_key.get_secret_value():
        capture_ai_trace(
            settings=settings,
            trace_id=run_id,
            span_name=f"repair.{feature}",
            root_span_id=root_span_id,
            extra_properties={
                "feature": feature,
                "project": project,
                "command": command,
                "pipeline": "repair",
            },
        )
    log = logger.bind(
        run_id=run_id,
        feature=feature,
        project=project,
        command=command,
        pipeline="repair",
        app=LOKI_APP_DEBUG,
        team=LOKI_TEAM_DEFAULT,
    )
    token = _repair_log.set(log)
    log.info(
        "Repair pipeline started feature={} project={} command={}",
        feature,
        project,
        command,
    )
    try:
        yield log
    finally:
        clear_pipeline_observability()
        _repair_log.reset(token)


def log_repair_step(
    step: str,
    *,
    status: str,
    duration_ms: float | None = None,
    **extra: Any,
) -> None:
    """Emit one repair step line to Loguru (and Loki when configured)."""
    payload: dict[str, Any] = {"step": step, "status": status, **extra}
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 1)
    repair_logger().bind(**payload).info("Repair step {} {}", step, status)
