"""Tests for repair pipeline structured step JSON parsing."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.schema_gate import parse_step_json
from figma_flutter_agent.dev.opencode.step_runner import OpenRouterStepRunner
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.openrouter_fusion import (
    build_fusion_invocation,
    build_single_invocation,
)


def test_parse_step_json_rejects_prose() -> None:
    with pytest.raises(LlmError, match="non-JSON structured output"):
        parse_step_json("Looking at this prompt, I need JSON", step="recognise")


def test_parse_step_json_accepts_fenced_json() -> None:
    payload = parse_step_json(
        '```json\n{"step": "recognise", "symptoms": []}\n```',
        step="recognise",
    )
    assert payload["step"] == "recognise"


def test_fusion_fallback_retries_with_judge_model(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings()

    fusion = build_fusion_invocation(
        fusion_model="openrouter/fusion",
        judge_model="deepseek/deepseek-v4-pro",
        analysis_models=("deepseek/deepseek-v4-pro", "xiaomi/mimo-v2.5-pro"),
    )
    single = build_single_invocation(model="deepseek/deepseek-v4-pro")
    responses = [
        "Not JSON at all",
        '{"step": "recognise", "symptoms": [{"id": "s1"}]}',
    ]

    client = MagicMock()
    client.complete_structured.side_effect = responses
    client._last_token_usage = {"input_tokens": 1, "output_tokens": 2}

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.create_openrouter_debug_client",
        lambda _settings, step, **kwargs: (client, fusion),
    )

    runner = OpenRouterStepRunner(settings)
    payload = runner.run_read_step(
        "recognise",
        board="forensic",
        run_context={"case_mode": "FORENSIC"},
        chain=ReasoningChain(),
        user_prompt="stub",
    )
    assert payload["symptoms"][0]["id"] == "s1"
    assert client.complete_structured.call_count == 2
    second_call = client.complete_structured.call_args_list[1]
    fallback_invocation = second_call.kwargs["invocation"]
    assert fallback_invocation.use_fusion is False
    assert fallback_invocation.model == single.model
    assert second_call.kwargs["analytics_span_name"] == "repair.recognise.fusion_fallback"


def test_fusion_transport_fallback_retries_on_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fusion panel transport failures should fall back to judge model before abort."""
    settings = load_settings()
    fusion = build_fusion_invocation(
        fusion_model="openrouter/fusion",
        judge_model="deepseek/deepseek-v4-pro",
        analysis_models=("deepseek/deepseek-v4-pro", "xiaomi/mimo-v2.5-pro"),
    )
    client = MagicMock()
    client.complete_structured.side_effect = [
        LlmError("OpenRouter structured completion failed: JSONDecodeError"),
        '{"step": "recognise", "symptoms": [{"id": "s1"}]}',
    ]
    client._last_token_usage = {"input_tokens": 1, "output_tokens": 2}

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.create_openrouter_debug_client",
        lambda _settings, step, **kwargs: (client, fusion),
    )

    runner = OpenRouterStepRunner(settings)
    payload = runner.run_read_step(
        "recognise",
        board="forensic",
        run_context={"case_mode": "FORENSIC"},
        chain=ReasoningChain(),
        user_prompt="stub",
    )
    assert payload["symptoms"][0]["id"] == "s1"
    assert client.complete_structured.call_count == 2
    second_call = client.complete_structured.call_args_list[1]
    fallback_invocation = second_call.kwargs["invocation"]
    assert fallback_invocation.use_fusion is False
    assert fallback_invocation.model == "deepseek/deepseek-v4-pro"
    assert second_call.kwargs["analytics_span_name"] == "repair.recognise.fusion_fallback"
