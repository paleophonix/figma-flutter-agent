"""Tests for PostHog LLM capture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
from pydantic import SecretStr

from figma_flutter_agent.config import Settings
from figma_flutter_agent.observability import posthog_llm


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
    sent: list[posthog_llm._CaptureJob] = []

    def _run_sync(job: posthog_llm._CaptureJob) -> None:
        sent.append(job)

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

    with patch.object(posthog_llm.httpx, "post") as mock_post:
        mock_post.return_value = httpx.Response(200, request=MagicMock())
        posthog_llm._send_capture(job)
    assert sent == []


def _sample_capture_job(
    *, span_name: str = "repair", trace_id: str = "run-2"
) -> posthog_llm._CaptureJob:
    return posthog_llm._CaptureJob(
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
        policy=posthog_llm._capture_policy(_settings_with_posthog()),
    )


def test_send_capture_retries_after_timeout() -> None:
    job = _sample_capture_job()
    ok_response = httpx.Response(200, request=MagicMock())
    with patch.object(posthog_llm.httpx, "post") as mock_post:
        mock_post.side_effect = [
            httpx.ReadTimeout("timed out"),
            ok_response,
        ]
        with patch.object(posthog_llm.time, "sleep"):
            posthog_llm._send_capture(job)
    assert mock_post.call_count == 2


def test_send_capture_gives_up_after_max_attempts() -> None:
    job = _sample_capture_job(span_name="generate", trace_id="run-2b")
    with patch.object(posthog_llm.httpx, "post", side_effect=httpx.ReadTimeout("timed out")):
        with patch.object(posthog_llm.time, "sleep"):
            with patch.object(posthog_llm.logger, "warning") as mock_warning:
                posthog_llm._send_capture(job)
    assert mock_warning.call_count >= _settings_with_posthog().posthog_capture_max_attempts
    assert "gave up" in mock_warning.call_args.args[0].lower()


def test_capture_policy_reads_env_fields() -> None:
    settings = Settings.model_construct(
        posthog_capture_max_attempts=5,
        posthog_capture_timeout_sec=12.0,
        posthog_capture_retry_base_sec=1.0,
    )
    policy = posthog_llm._capture_policy(settings)
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
