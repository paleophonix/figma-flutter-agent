"""LLM reusable widget candidate detection."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.llm.semantic_context import assemble_semantic_context
from figma_flutter_agent.pipeline.reusable_cache import (
    load_cached_reusable_candidates,
    reusable_candidates_cache_key,
    write_cached_reusable_candidates,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens
from figma_flutter_agent.schemas.reusable_candidates import ReusableWidgetCandidate

_REUSABLE_CANDIDATES_SYSTEM = """You propose reusable Flutter widget extraction candidates from a Figma screen.
Output ONLY valid JSON matching the schema.
Rules:
- Cite existing figma node ids from the provided tree outline only.
- Do not emit Dart, widgetIr, or screen layout.
- Prefer repeated card/list-item/button families over layout wrappers.
- Include confidence in [0,1] and brief reason text.
- suggestedParams must use valid Dart identifier names when props differ across instances.
"""


def build_reusable_candidates_user_payload(
    *,
    feature_name: str,
    clean_tree: CleanDesignTreeNode,
    cluster_summary: dict[str, int],
    widget_hints: list[str],
    max_candidates: int,
) -> str:
    """Build the user payload for reusable widget candidate detection."""
    packet = assemble_semantic_context(clean_tree)
    payload: dict[str, Any] = {
        "featureName": feature_name,
        "clusterSummary": cluster_summary,
        "widgetExtractionHints": widget_hints,
        "maxCandidates": max_candidates,
        **packet.model_dump_for_llm(),
    }
    return json.dumps(payload, separators=(",", ":"))


async def resolve_reusable_candidates(
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    *,
    config: WidgetExtractionConfig,
    cluster_summary: dict[str, int],
    widget_hints: list[str],
    settings: Settings,
    project_dir: Path,
    feature_name: str,
    llm_client_factory: Callable[[Settings], Any],
    force_refresh: bool = False,
) -> list[ReusableWidgetCandidate]:
    """Return gated LLM reusable candidates, using disk cache when available."""
    if not config.ai_reusable.enabled:
        return []

    cache_key = reusable_candidates_cache_key(clean_tree, tokens, config)
    if not force_refresh:
        cached = load_cached_reusable_candidates(
            project_dir,
            feature_name,
            cache_key=cache_key,
        )
        if cached is not None:
            return list(cached.candidates)

    from figma_flutter_agent.generator.widget_extraction.policy import effective_ai_reusable_limits

    _, max_candidates = effective_ai_reusable_limits(config)
    client = llm_client_factory(settings)
    response = await client.reusable_candidates_async(
        clean_tree,
        feature_name=feature_name,
        cluster_summary=cluster_summary,
        widget_hints=widget_hints,
        max_candidates=max_candidates,
    )
    write_cached_reusable_candidates(
        project_dir,
        feature_name,
        cache_key=cache_key,
        response=response,
    )
    logger.bind(feature=feature_name, count=len(response.candidates)).info(
        "Resolved reusable widget candidates via LLM"
    )
    return list(response.candidates)


def build_ai_reusable_hints(
    root: CleanDesignTreeNode,
    candidates: list[ReusableWidgetCandidate],
    *,
    config: WidgetExtractionConfig,
    widget_suffix: str,
) -> list[str]:
    """Build LLM widget extraction hints from gated suggest-mode candidates."""
    from figma_flutter_agent.generator.widget_extraction.gates import (
        gate_reusable_candidate,
        normalize_widget_class_name,
    )

    hints: list[str] = []
    claimed_class_names: set[str] = set()
    claimed_node_ids: set[str] = set()
    for candidate in candidates:
        node = gate_reusable_candidate(
            candidate,
            config=config,
            root=root,
            widget_suffix=widget_suffix,
            claimed_class_names=claimed_class_names,
            claimed_node_ids=claimed_node_ids,
        )
        if node is None:
            continue
        class_name = normalize_widget_class_name(candidate.widget_name, widget_suffix=widget_suffix)
        if class_name is None:
            continue
        hints.append(
            f"AI-assisted reusable candidate {class_name!r} at node "
            f"{candidate.node_id} (confidence {candidate.confidence:.2f}): "
            f"{candidate.reason}; emit kind=extracted with matching widgetIr."
        )
        claimed_class_names.add(class_name)
        claimed_node_ids.add(candidate.node_id)
    return hints
