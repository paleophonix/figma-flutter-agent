"""Parse OpenRouter usage/cost fields from chat completion responses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenRouterUsageCost:
    """USD cost fields reported by OpenRouter ``usage``."""

    total_cost_usd: float | None
    input_cost_usd: float | None
    output_cost_usd: float | None


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def parse_usage_dict(usage: dict[str, Any] | None) -> OpenRouterUsageCost:
    """Parse OpenRouter cost fields from a raw ``usage`` object.

    Args:
        usage: ``usage`` dict from an OpenRouter chat completion body.

    Returns:
        Parsed cost fields (any may be ``None`` when absent).
    """
    if not usage:
        return OpenRouterUsageCost(None, None, None)
    details = usage.get("cost_details")
    details_dict = details if isinstance(details, dict) else {}
    return OpenRouterUsageCost(
        total_cost_usd=_coerce_float(usage.get("cost")),
        input_cost_usd=_coerce_float(details_dict.get("upstream_inference_prompt_cost")),
        output_cost_usd=_coerce_float(details_dict.get("upstream_inference_completions_cost")),
    )


def parse_usage_from_response_text(raw_text: str) -> OpenRouterUsageCost:
    """Parse OpenRouter usage cost from the raw HTTP response body.

    Args:
        raw_text: JSON body returned by OpenRouter chat completions.

    Returns:
        Parsed cost fields, or empty values when JSON/usage is missing.
    """
    try:
        body = json.loads(raw_text)
    except json.JSONDecodeError:
        return OpenRouterUsageCost(None, None, None)
    usage = body.get("usage")
    if isinstance(usage, dict):
        return parse_usage_dict(usage)
    return OpenRouterUsageCost(None, None, None)
