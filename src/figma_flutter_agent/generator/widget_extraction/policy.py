"""Widget extraction policy resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.config.models import WidgetExtractionConfig

WidgetExtractionPolicyName = Literal[
    "off",
    "dedup",
    "annotated",
    "balanced",
    "auto_reusable",
    "aggressive",
]


@dataclass(frozen=True)
class WidgetExtractionSources:
    """Enabled widget extraction source channels for a policy."""

    annotation: bool
    repetition: bool
    inference: bool


def inference_enabled(config: WidgetExtractionConfig) -> bool:
    """Return whether the inference candidate channel is active."""
    return config.policy in {"auto_reusable", "aggressive"} or config.ai_reusable.enabled


def resolve_widget_extraction_sources(
    config: WidgetExtractionConfig,
) -> WidgetExtractionSources:
    """Map a configured policy to enabled extraction sources."""
    policy = config.policy
    inference = inference_enabled(config)
    if policy == "off":
        return WidgetExtractionSources(annotation=False, repetition=False, inference=False)
    if policy == "dedup":
        return WidgetExtractionSources(annotation=False, repetition=True, inference=inference)
    if policy == "annotated":
        return WidgetExtractionSources(annotation=True, repetition=False, inference=inference)
    if policy == "balanced":
        return WidgetExtractionSources(
            annotation=True,
            repetition=True,
            inference=inference,
        )
    if policy in {"auto_reusable", "aggressive"}:
        return WidgetExtractionSources(annotation=True, repetition=True, inference=True)
    return WidgetExtractionSources(annotation=True, repetition=True, inference=inference)


def effective_ai_reusable_limits(
    config: WidgetExtractionConfig,
) -> tuple[float, int]:
    """Return min confidence and max candidates with aggressive policy scaling."""
    ai = config.ai_reusable
    min_confidence = ai.min_confidence
    max_candidates = ai.max_candidates
    if config.policy == "aggressive":
        min_confidence *= 0.9
        max_candidates = min(24, int(max_candidates * 1.5))
    return min_confidence, max_candidates


def inference_extracts_to_specs(config: WidgetExtractionConfig) -> bool:
    """Return whether gated inference candidates become cluster widget specs."""
    if config.policy in {"auto_reusable", "aggressive"}:
        return True
    return config.ai_reusable.enabled and config.ai_reusable.mode == "enforce"


def effective_min_count(
    config: WidgetExtractionConfig,
    *,
    legacy_min_count: int,
) -> int:
    """Return cluster min count honoring legacy generation settings."""
    if config.min_count > 0:
        return config.min_count
    return legacy_min_count


def enforce_cluster_widgets_for_policy(config: WidgetExtractionConfig) -> bool:
    """Return whether cluster widget files should be generated."""
    return config.policy != "off"
