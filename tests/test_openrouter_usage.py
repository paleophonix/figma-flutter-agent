"""Tests for OpenRouter usage/cost parsing."""

from __future__ import annotations

from figma_flutter_agent.llm.openrouter_usage import (
    OpenRouterUsageCost,
    parse_usage_dict,
    parse_usage_from_response_text,
)


def test_parse_usage_dict_reads_cost_and_breakdown() -> None:
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "cost": 0.00042,
        "cost_details": {
            "upstream_inference_prompt_cost": 0.0001,
            "upstream_inference_completions_cost": 0.00032,
        },
    }
    parsed = parse_usage_dict(usage)
    assert parsed == OpenRouterUsageCost(
        total_cost_usd=0.00042,
        input_cost_usd=0.0001,
        output_cost_usd=0.00032,
    )


def test_parse_usage_from_response_text() -> None:
    raw = """
    {
      "choices": [{"message": {"content": "{}"}}],
      "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cost": 0.0015
      }
    }
    """
    parsed = parse_usage_from_response_text(raw)
    assert parsed.total_cost_usd == 0.0015
