"""Tests for PostHog LLM capture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
from pydantic import SecretStr

from figma_flutter_agent.config import Settings
from figma_flutter_agent.observability import posthog_llm
from figma_flutter_agent.observability.posthog_transport import capture_policy_from


def _settings_with_posthog() -> Settings:
    return Settings.model_construct(
        posthog_api_key=SecretStr("phc_test"),
        posthog_host="https://us.i.posthog.com",
        posthog_capture_max_attempts=3,
        posthog_capture_timeout_sec=8.0,
        posthog_capture_retry_base_sec=0.75,
    )


def test_capture_ai_generation_queues_background_thread() -> None:
    settings = _settings_with_posthog()

    with patch.object(posthog_llm.threading, "Thread") as mock_thread:
        mock_thread.return_value.start = MagicMock()
        posthog_llm.capture_ai_generation(
            settings=settings,
            trace_id="run-1",
            span_name="repair",
            provider="openrouter",
            model="google/gemini-3-flash-preview",
            latency_sec=1.2,
            system_prompt="sys",
            user_prompt="user",
            output_text='{"ok": true}',
            is_error=False,
        )
        mock_thread.assert_called_once()
        assert mock_thread.call_args.kwargs["name"] == "posthog-llm-repair"
        job = mock_thread.call_args.kwargs["args"][0]
        assert job.span_name == "repair"
        assert job.trace_id == "run-1"

    with patch("figma_flutter_agent.observability.posthog_transport.httpx.post") as mock_post:
        mock_post.return_value = httpx.Response(200, request=MagicMock())
        posthog_llm._send_llm_capture(job)


def _sample_capture_job(
    *, span_name: str = "repair", trace_id: str = "run-2"
) -> posthog_llm._LlmCaptureJob:
    return posthog_llm._LlmCaptureJob(
        api_key="phc_test",
        host="https://us.i.posthog.com",
        trace_id=trace_id,
        span_name=span_name,
        provider="openrouter",
        model="m",
        latency_sec=0.1,
        system_prompt="s",
        user_prompt="u",
        output_text=None,
        is_error=False,
        error_message=None,
        input_tokens=None,
        output_tokens=None,
        total_cost_usd=None,
        input_cost_usd=None,
        output_cost_usd=None,
        span_id="run-2:repair:001",
        parent_span_id="run-2:root",
        extra_properties=None,
        policy=capture_policy_from(_settings_with_posthog()),
    )


def test_build_llm_properties_includes_openrouter_cost() -> None:
    job = posthog_llm._LlmCaptureJob(
        api_key="phc_test",
        host="https://us.i.posthog.com",
        trace_id="run-cost",
        span_name="repair.recognise",
        provider="openrouter",
        model="deepseek/deepseek-v4-pro",
        latency_sec=2.5,
        system_prompt="sys",
        user_prompt="user",
        output_text="{}",
        is_error=False,
        error_message=None,
        input_tokens=1200,
        output_tokens=80,
        total_cost_usd=0.0031,
        input_cost_usd=0.0024,
        output_cost_usd=0.0007,
        span_id="run-cost:repair.recognise:001",
        parent_span_id="run-cost:root",
        extra_properties={"repair_step_count": 3},
        policy=capture_policy_from(_settings_with_posthog()),
    )
    props = posthog_llm._build_llm_properties(job)
    assert props["$ai_total_cost_usd"] == 0.0031
    assert props["repair_step_count"] == 3
    assert props["$ai_input_cost_usd"] == 0.0024
    assert props["$ai_output_cost_usd"] == 0.0007
    assert props["$ai_parent_id"] == "run-cost:root"
    assert props["$ai_span_id"] == "run-cost:repair.recognise:001"


def test_capture_ai_trace_queues_root_event() -> None:
    settings = _settings_with_posthog()
    with patch.object(posthog_llm.threading, "Thread") as mock_thread:
        mock_thread.return_value.start = MagicMock()
        posthog_llm.capture_ai_trace(
            settings=settings,
            trace_id="run-trace",
            span_name="repair.sign_up",
            root_span_id="run-trace:root",
            extra_properties={"feature": "sign_up"},
        )
        mock_thread.assert_called_once()
        request = mock_thread.call_args.kwargs["args"][0]
        assert request.event == "$ai_trace"
        assert request.properties["$ai_trace_id"] == "run-trace"
        assert request.properties["$ai_span_id"] == "run-trace:root"
        assert request.properties["$ai_span_name"] == "repair.sign_up"
        assert request.properties["feature"] == "sign_up"


def test_send_capture_retries_after_timeout() -> None:
    job = _sample_capture_job()
    ok_response = httpx.Response(200, request=MagicMock())
    with patch("figma_flutter_agent.observability.posthog_transport.httpx.post") as mock_post:
        mock_post.side_effect = [
            httpx.ReadTimeout("timed out"),
            ok_response,
        ]
        with patch("figma_flutter_agent.observability.posthog_transport.time.sleep"):
            posthog_llm._send_llm_capture(job)
    assert mock_post.call_count == 2


def test_send_capture_gives_up_after_max_attempts() -> None:
    job = _sample_capture_job(span_name="generate", trace_id="run-2b")
    with patch(
        "figma_flutter_agent.observability.posthog_transport.httpx.post",
        side_effect=httpx.ReadTimeout("timed out"),
    ):
        with patch("figma_flutter_agent.observability.posthog_transport.time.sleep"):
            with patch(
                "figma_flutter_agent.observability.posthog_transport.logger.warning"
            ) as mock_warning:
                posthog_llm._send_llm_capture(job)
    assert mock_warning.call_count >= _settings_with_posthog().posthog_capture_max_attempts
    assert "gave up" in mock_warning.call_args.args[0].lower()


def test_capture_policy_reads_env_fields() -> None:
    settings = Settings.model_construct(
        posthog_capture_max_attempts=5,
        posthog_capture_timeout_sec=12.0,
        posthog_capture_retry_base_sec=1.0,
    )
    policy = capture_policy_from(settings)
    assert policy.max_attempts == 5
    assert policy.timeout_sec == 12.0
    assert policy.retry_base_sec == 1.0


def test_capture_skipped_without_api_key() -> None:
    settings = Settings.model_construct(posthog_api_key=SecretStr(""))
    with patch.object(posthog_llm.threading, "Thread") as mock_thread:
        posthog_llm.capture_ai_generation(
            settings=settings,
            trace_id="run-3",
            span_name="generate",
            provider="openrouter",
            model="m",
            latency_sec=0.1,
            system_prompt="s",
            user_prompt="u",
            output_text=None,
            is_error=False,
        )
        mock_thread.assert_not_called()
