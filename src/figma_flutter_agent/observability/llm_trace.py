"""Context for correlating LLM calls with a pipeline run (PostHog, logs)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from figma_flutter_agent.config import Settings

_run_id: ContextVar[str] = ContextVar("figma_run_id", default="")
_llm_span_name: ContextVar[str] = ContextVar("figma_llm_span_name", default="generate")
_trace_root_span_id: ContextVar[str] = ContextVar("figma_trace_root_span_id", default="")
_generation_seq: ContextVar[int] = ContextVar("figma_ai_generation_seq", default=0)
_settings: ContextVar[Settings | None] = ContextVar("figma_settings", default=None)


@dataclass(frozen=True)
class LlmTraceContext:
    """Active pipeline correlation for LLM analytics."""

    run_id: str
    span_name: str
    settings: Settings
    root_span_id: str | None


def pipeline_root_span_id(run_id: str) -> str:
    """Return the stable parent span id for one pipeline run."""
    return f"{run_id}:root"


def bind_pipeline_observability(*, run_id: str, settings: Settings) -> str:
    """Bind run id and settings for downstream LLM capture.

    Args:
        run_id: Correlation id shared by all LLM calls in one pipeline run.
        settings: Loaded application settings.

    Returns:
        Root span id used as ``$ai_parent_id`` for child generations.
    """
    root_span_id = pipeline_root_span_id(run_id)
    _run_id.set(run_id)
    _trace_root_span_id.set(root_span_id)
    _generation_seq.set(0)
    _settings.set(settings)
    return root_span_id


def clear_pipeline_observability() -> None:
    """Reset pipeline correlation context (used by tests and CLI teardown)."""
    _run_id.set("")
    _settings.set(None)
    _llm_span_name.set("generate")
    _trace_root_span_id.set("")
    _generation_seq.set(0)


def set_llm_stage(span_name: str) -> None:
    """Set PostHog ``$ai_span_name`` for the next LLM call (generate, repair, refine)."""
    _llm_span_name.set(span_name)


def current_trace_root_span_id() -> str | None:
    """Return the active pipeline root span id when observability is bound."""
    value = _trace_root_span_id.get()
    return value or None


def next_generation_span_id(*, trace_id: str, span_name: str) -> str:
    """Allocate a unique child span id under one pipeline trace."""
    seq = _generation_seq.get() + 1
    _generation_seq.set(seq)
    safe_span = span_name.replace(" ", "_")
    return f"{trace_id}:{safe_span}:{seq:03d}"


def repair_pipeline_posthog_from_recorder() -> bool:
    """Return True when repair read-step PostHog is owned by ``RepairTraceRecorder``."""
    settings = _settings.get()
    if settings is None or not _run_id.get():
        return False
    return settings.agent.debug_pipeline.trace.posthog


def current_llm_trace_context() -> LlmTraceContext | None:
    """Return the active trace context when pipeline observability is bound."""
    settings = _settings.get()
    run_id = _run_id.get()
    if settings is None or not run_id:
        return None
    root_span_id = current_trace_root_span_id()
    return LlmTraceContext(
        run_id=run_id,
        span_name=_llm_span_name.get(),
        settings=settings,
        root_span_id=root_span_id,
    )
