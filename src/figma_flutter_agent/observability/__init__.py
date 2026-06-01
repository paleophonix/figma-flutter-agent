"""Structured observability helpers for pipeline and CLI runs."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from figma_flutter_agent.errors import FigmaFlutterError, format_error_for_log

__all__ = ["log_ast_reconcile_session_summary", "log_stage", "new_run_id"]


def log_ast_reconcile_session_summary(log: Any) -> None:
    """Log a one-line summary of the AST reconcile cache for this pipeline run.

    Args:
        log: Bound Loguru logger for the current run.
    """
    from figma_flutter_agent.generator.reconcile_ast_cache import ast_reconcile_cache_stats

    hits, paths, subprocess_calls = ast_reconcile_cache_stats()
    log.info(
        "AST reconcile cache (run): {} subprocess call(s), {} cache hit(s), {} unique path(s)",
        subprocess_calls,
        hits,
        paths,
    )


def new_run_id() -> str:
    """Return a short correlation id for one pipeline/CLI run."""
    return uuid.uuid4().hex[:12]


@contextmanager
def log_stage(log: Any, stage: str, **extra: Any) -> Iterator[None]:
    """Log stage start/end with ``duration_ms`` in structured context.

    Args:
        log: Bound Loguru logger (typically includes file_key / feature_name / run_id).
        stage: Short stage name (fetch, parse, llm, plan, validate, write).
        **extra: Additional bind keys for this stage only.
    """
    stage_log = log.bind(stage=stage, **extra)
    stage_log.info("Stage {} started", stage)
    started = time.perf_counter()
    try:
        yield
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        stage_log.bind(duration_ms=duration_ms).info("Stage {} completed", stage)
    except FigmaFlutterError as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        stage_log.bind(duration_ms=duration_ms).error(
            "Stage {} failed: {}",
            stage,
            format_error_for_log(exc),
        )
        raise
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        stage_log.bind(duration_ms=duration_ms).exception("Stage {} failed", stage)
        raise
