"""LLM reasoning/thinking configuration and provider payload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LlmReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]

_VALID_EFFORTS: frozenset[str] = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh"},
)

_REASONING_ERROR_MARKERS: frozenset[str] = frozenset(
    {
        "reasoning",
        "thinking",
        "thinking_level",
        "thinkingbudget",
        "thinking_budget",
        "budget_tokens",
        "output_config",
        "effort",
    },
)


@dataclass(frozen=True)
class LlmReasoningSettings:
    """Optional reasoning controls loaded from environment."""

    effort: LlmReasoningEffort | None = None
    max_tokens: int | None = None
    exclude: bool | None = None

    def is_active(self) -> bool:
        """Return True when any reasoning knob should be sent to the provider."""
        if self.max_tokens is not None:
            return True
        return self.effort is not None and self.effort != "none"

    def openrouter_payload(self) -> dict[str, object] | None:
        """Build OpenRouter/OpenAI-compatible ``reasoning`` object."""
        if not self.is_active():
            return None
        payload: dict[str, object] = {}
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        elif self.effort is not None:
            payload["effort"] = self.effort
        if self.exclude is not None:
            payload["exclude"] = self.exclude
        return payload

    def anthropic_create_kwargs(self, *, max_output_tokens: int) -> dict[str, object]:
        """Build Anthropic Messages API thinking kwargs."""
        if not self.is_active():
            return {}
        if self.max_tokens is not None:
            budget = max(1024, self.max_tokens)
            output_cap = max(max_output_tokens, budget + 1024)
            return {
                "thinking": {"type": "enabled", "budget_tokens": budget},
                "max_tokens": output_cap,
            }
        effort = self.effort or "medium"
        if effort == "minimal":
            effort = "low"
        if effort == "none":
            return {}
        if effort == "xhigh":
            effort = "high"
        return {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        }


def normalize_reasoning_effort(value: object) -> LlmReasoningEffort | None:
    """Parse ``LLM_REASONING_EFFORT``; invalid values become ``None`` (safe default)."""
    if value == "" or value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized not in _VALID_EFFORTS:
        return None
    return normalized  # type: ignore[return-value]


def normalize_reasoning_max_tokens(value: object) -> int | None:
    """Parse ``LLM_REASONING_MAX_TOKENS``; invalid values become ``None``."""
    if value == "" or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def is_reasoning_parameter_rejection(*, status_code: int | None, message: str) -> bool:
    """Heuristic: provider rejected optional reasoning/thinking parameters."""
    if status_code not in {400, 422}:
        return False
    lower = message.lower()
    if any(marker in lower for marker in _REASONING_ERROR_MARKERS):
        return True
    return "unknown parameter" in lower and any(
        token in lower for token in ("reasoning", "thinking", "effort", "budget")
    )


_TRANSPORT_FAILURE_MARKERS: frozenset[str] = frozenset(
    {
        "timeout",
        "timed out",
        "time-out",
        "connecttimeout",
        "readtimeout",
        "apitimeout",
        "connection error",
        "connection refused",
        "connection reset",
        "network",
        "unreachable",
        "temporarily unavailable",
    },
)


def is_likely_transport_failure(*, status_code: int | None, message: str) -> bool:
    """Heuristic: no HTTP status — timeout or connection failure talking to the provider."""
    if status_code is not None:
        return status_code in {408, 504}
    lower = message.lower()
    return any(marker in lower for marker in _TRANSPORT_FAILURE_MARKERS)


def should_fallback_without_reasoning(*, status_code: int | None, message: str) -> bool:
    """Return True when the same request may succeed without reasoning kwargs.

    Used for customer deployments where provider, model, and reasoning knobs vary.
    """
    return is_reasoning_parameter_rejection(
        status_code=status_code, message=message
    ) or is_likely_transport_failure(status_code=status_code, message=message)
