"""Semantic widget extraction candidates (static scorer + gated LLM)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.widget_extraction.gates import (
    gate_reusable_candidate,
    gate_scored_candidate,
    normalize_widget_class_name,
)
from figma_flutter_agent.generator.widget_extraction.policy import (
    effective_ai_reusable_limits,
    inference_extracts_to_specs,
)
from figma_flutter_agent.generator.widget_extraction.scorer import score_static_candidates
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.schemas.reusable_candidates import ReusableWidgetCandidate


@dataclass(frozen=True)
class InferenceCandidate:
    """Gated inference extraction target with optional LLM naming."""

    node: CleanDesignTreeNode
    widget_name: str
    score: float
    source: str
    suggested_params: tuple[str, ...] = ()


def discover_semantic_candidates(
    root: CleanDesignTreeNode,
    *,
    config: WidgetExtractionConfig,
    llm_candidates: list[ReusableWidgetCandidate] | None = None,
    widget_suffix: str = "Widget",
    legacy_min_count: int = 2,
    claimed_class_names: set[str] | None = None,
    claimed_node_ids: set[str] | None = None,
) -> list[InferenceCandidate]:
    """Return gated inference candidates when the inference channel is enabled."""
    if not inference_extracts_to_specs(config):
        return []

    class_names = set(claimed_class_names or ())
    node_ids = set(claimed_node_ids or ())
    results: list[InferenceCandidate] = []
    seen_node_ids: set[str] = set()

    for scored in score_static_candidates(
        root,
        config=config,
        legacy_min_count=legacy_min_count,
    ):
        node = gate_scored_candidate(
            scored,
            config=config,
            root=root,
            widget_suffix=widget_suffix,
            claimed_class_names=class_names,
            claimed_node_ids=node_ids,
            legacy_min_count=legacy_min_count,
        )
        if node is None or node.id in seen_node_ids:
            continue
        from figma_flutter_agent.generator.widget_extraction.naming import fallback_class_name

        widget_name = fallback_class_name(node, widget_suffix)
        results.append(
            InferenceCandidate(
                node=node,
                widget_name=widget_name,
                score=scored.score,
                source="static",
            )
        )
        seen_node_ids.add(node.id)
        class_names.add(widget_name)
        node_ids.add(node.id)

    if llm_candidates:
        _, max_candidates = effective_ai_reusable_limits(config)
        for llm_candidate in llm_candidates[:max_candidates]:
            node = gate_reusable_candidate(
                llm_candidate,
                config=config,
                root=root,
                widget_suffix=widget_suffix,
                claimed_class_names=class_names,
                claimed_node_ids=node_ids,
                legacy_min_count=legacy_min_count,
            )
            if node is None or node.id in seen_node_ids:
                continue
            widget_name = normalize_widget_class_name(
                llm_candidate.widget_name,
                widget_suffix=widget_suffix,
            )
            if widget_name is None:
                continue
            results.append(
                InferenceCandidate(
                    node=node,
                    widget_name=widget_name,
                    score=llm_candidate.confidence,
                    source="llm",
                    suggested_params=tuple(llm_candidate.suggested_params),
                )
            )
            seen_node_ids.add(node.id)
            class_names.add(widget_name)
            node_ids.add(node.id)

    return results
