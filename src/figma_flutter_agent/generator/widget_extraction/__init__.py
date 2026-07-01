"""Widget extraction policy and unified spec collection."""

from figma_flutter_agent.generator.widget_extraction.collect import collect_widget_specs
from figma_flutter_agent.generator.widget_extraction.policy import (
    WidgetExtractionSources,
    effective_ai_reusable_limits,
    inference_enabled,
    inference_extracts_to_specs,
    resolve_widget_extraction_sources,
)
from figma_flutter_agent.generator.widget_extraction.semantic import (
    InferenceCandidate,
    discover_semantic_candidates,
)

__all__ = [
    "InferenceCandidate",
    "WidgetExtractionSources",
    "collect_widget_specs",
    "discover_semantic_candidates",
    "effective_ai_reusable_limits",
    "inference_enabled",
    "inference_extracts_to_specs",
    "resolve_widget_extraction_sources",
]
