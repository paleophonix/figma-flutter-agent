"""Tests for pipeline-level PostHog trace correlation."""

from __future__ import annotations

from unittest.mock import patch

from pydantic import SecretStr

from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig, DebugPipelineTraceConfig
from figma_flutter_agent.config.models import AgentYamlConfig
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.dev.opencode.repair_log import bind_repair_observability
from figma_flutter_agent.observability.llm_trace import (
    clear_pipeline_observability,
    current_llm_trace_context,
    current_trace_root_span_id,
    next_generation_span_id,
    pipeline_root_span_id,
)


def test_pipeline_root_span_id_stable() -> None:
    assert pipeline_root_span_id("abc123") == "abc123:root"


def test_generation_span_ids_unique_under_one_trace() -> None:
    clear_pipeline_observability()
    first = next_generation_span_id(trace_id="run1", span_name="repair.recognise")
    second = next_generation_span_id(trace_id="run1", span_name="repair.diagnose")
    assert first != second
    assert first.startswith("run1:repair.recognise:")
    assert second.startswith("run1:repair.diagnose:")


def test_bind_repair_observability_emits_single_root_trace() -> None:
    settings = Settings.model_construct(
        agent=AgentYamlConfig(
            debug_pipeline=DebugPipelineConfig(
                trace=DebugPipelineTraceConfig(posthog=True),
            ),
        ),
        posthog_api_key=SecretStr("phc_test"),
        posthog_host="https://us.i.posthog.com",
    )
    with patch("figma_flutter_agent.dev.opencode.repair_log.capture_ai_trace") as mock_trace:
        with bind_repair_observability(
            run_id="run-repair",
            feature="sign_up",
            project="limbo",
            command="wizard_debug",
            settings=settings,
        ):
            assert current_trace_root_span_id() == "run-repair:root"
            ctx = current_llm_trace_context()
            assert ctx is not None
            assert ctx.run_id == "run-repair"
        mock_trace.assert_called_once()
        assert mock_trace.call_args.kwargs["trace_id"] == "run-repair"
        assert mock_trace.call_args.kwargs["span_name"] == "repair.sign_up"
        assert mock_trace.call_args.kwargs["root_span_id"] == "run-repair:root"

    clear_pipeline_observability()
