"""Tier-1 property signals from component variants (no layer names)."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.models import TierSignals
from figma_flutter_agent.parser.semantics.signals.type_trust import semantic_signal_type
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_VARIANT_AXIS_KEYS = frozenset({"type", "role", "variant", "component", "control", "state"})


def collect_property_signals(node: CleanDesignTreeNode) -> TierSignals:
    """Collect tier-1 signals from ``ComponentVariant`` metadata."""
    hits: dict[str, object] = {}
    score = 0.0
    overlay = semantic_signal_type(node) == NodeType.DIALOG
    variant = node.variant
    if variant is not None:
        if variant.component_id:
            hits["component_id"] = variant.component_id
            score = max(score, 0.5)
        for key, value in variant.variant_properties.items():
            normalized_key = key.lower().strip()
            if normalized_key in _VARIANT_AXIS_KEYS:
                hits[f"variant.{normalized_key}"] = value
                score = max(score, 0.85)
        if variant.state:
            hits["variant.state"] = variant.state
            score = max(score, 0.75)
    if overlay:
        hits["overlay"] = True
        score = max(score, 0.9)
    return TierSignals(
        properties_score=min(score, 1.0),
        property_hits=hits,
        overlay_signal=overlay,
    )
