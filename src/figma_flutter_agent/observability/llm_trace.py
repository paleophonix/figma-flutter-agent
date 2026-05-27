"""Context for correlating LLM calls with a pipeline run (PostHog, logs)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from figma_flutter_agent.config import Settings

_run_id: ContextVar[str] = ContextVar("figma_run_id", default="")
_llm_span_name: ContextVar[str] = ContextVar("figma_llm_span_name", default="generate")
_settings: ContextVar[Settings | None] = ContextVar("figma_settings", default=None)


@dataclass(frozen=True)
class LlmTraceContext:
    """Active pipeline correlation for LLM analytics."""

    run_id: str
    span_name: str
    settings: Settings


def bind_pipeline_observability(*, run_id: str, settings: Settings) -> None:
    """Bind run id and settings for downstream LLM capture."""
    _run_id.set(run_id)
    _settings.set(settings)


def set_llm_stage(span_name: str) -> None:
    """Set PostHog ``$ai_span_name`` for the next LLM call (generate, repair, refine)."""
    _llm_span_name.set(span_name)


def current_llm_trace_context() -> LlmTraceContext | None:
    """Return the active trace context when pipeline observability is bound."""
    settings = _settings.get()
    run_id = _run_id.get()
    if settings is None or not run_id:
        return None
    return LlmTraceContext(run_id=run_id, span_name=_llm_span_name.get(), settings=settings)
