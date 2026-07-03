"""Cluster extraction bijection and definition identity (Program 04)."""

from figma_flutter_agent.generator.extraction.bijection_plan import (
    ClusterExtractionPlan,
    enforce_extraction_bijection,
    validate_extraction_bijection_shadow,
)
from figma_flutter_agent.generator.extraction.definition_key import (
    DefinitionKey,
    compare_definition_key_shadow,
    lookup_cluster_class_authoritative,
)

__all__ = [
    "ClusterExtractionPlan",
    "DefinitionKey",
    "compare_definition_key_shadow",
    "enforce_extraction_bijection",
    "lookup_cluster_class_authoritative",
    "validate_extraction_bijection_shadow",
]
