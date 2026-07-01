"""LLM cluster widget naming enrichment."""

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
    load_cached_widget_enrich,
    reusable_candidates_cache_key,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens
from figma_flutter_agent.schemas.reusable_candidates import WidgetEnrichResponse

_WIDGET_ENRICH_SYSTEM = """You suggest human-readable Flutter widget class names and constructor parameter labels.
Output ONLY valid JSON matching the schema.
Rules:
- widgetName must be PascalCase and end with Widget when widgetSuffix is provided.
- paramRenames maps existing generic param names to meaningful Dart identifiers.
- Do not invent geometry or node ids; only rename clusters listed in entries.
"""


def build_widget_enrich_user_payload(
    *,
    feature_name: str,
    clean_tree: CleanDesignTreeNode,
    entries: list[dict[str, Any]],
    widget_suffix: str,
) -> str:
    """Build user payload for cluster widget naming enrichment."""
    packet = assemble_semantic_context(clean_tree)
    payload: dict[str, Any] = {
        "featureName": feature_name,
        "widgetSuffix": widget_suffix,
        "entries": entries,
        **packet.model_dump_for_llm(),
    }
    return json.dumps(payload, separators=(",", ":"))


def resolve_widget_enrich_sync(
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    *,
    entries: list[dict[str, Any]],
    config: WidgetExtractionConfig,
    settings: Settings,
    project_dir: Path,
    feature_name: str,
    widget_suffix: str,
    llm_client_factory: Callable[[Settings], Any],
    force_refresh: bool = False,
) -> WidgetEnrichResponse | None:
    """Return synchronous LLM naming enrichment for cluster widgets."""
    enrich_cfg = config.enrich
    if not enrich_cfg.enabled and not entries:
        return None

    cache_key = reusable_candidates_cache_key(clean_tree, tokens, config)
    if enrich_cfg.cache_by_subtree_hash and not force_refresh:
        cached = load_cached_widget_enrich(project_dir, feature_name, cache_key=cache_key)
        if cached is not None:
            return WidgetEnrichResponse.model_validate(cached)

    client = llm_client_factory(settings)
    response = client._execute_widget_enrich(
        feature_name=feature_name,
        clean_tree=clean_tree,
        entries=entries,
        widget_suffix=widget_suffix,
    )
    if enrich_cfg.cache_by_subtree_hash:
        from figma_flutter_agent.pipeline.reusable_cache import WIDGET_ENRICH_JSON, screen_root

        path = screen_root(project_dir, feature_name) / WIDGET_ENRICH_JSON
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "cacheKey": cache_key,
                    "response": response.model_dump(by_alias=True, mode="json"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    logger.bind(feature=feature_name, count=len(response.entries)).info(
        "Resolved widget enrich suggestions via LLM"
    )
    return response


async def resolve_widget_enrich(
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    *,
    entries: list[dict[str, Any]],
    config: WidgetExtractionConfig,
    settings: Settings,
    project_dir: Path,
    feature_name: str,
    widget_suffix: str,
    llm_client_factory: Callable[[Settings], Any],
    force_refresh: bool = False,
) -> WidgetEnrichResponse | None:
    """Return LLM naming enrichment for cluster widgets."""
    enrich_cfg = config.enrich
    if not enrich_cfg.enabled and not entries:
        return None

    cache_key = reusable_candidates_cache_key(clean_tree, tokens, config)
    if enrich_cfg.cache_by_subtree_hash and not force_refresh:
        cached = load_cached_widget_enrich(project_dir, feature_name, cache_key=cache_key)
        if cached is not None:
            return WidgetEnrichResponse.model_validate(cached)

    client = llm_client_factory(settings)
    response = await client.widget_enrich_async(
        clean_tree,
        feature_name=feature_name,
        entries=entries,
        widget_suffix=widget_suffix,
    )
    if enrich_cfg.cache_by_subtree_hash:
        from figma_flutter_agent.pipeline.reusable_cache import WIDGET_ENRICH_JSON, screen_root

        path = screen_root(project_dir, feature_name) / WIDGET_ENRICH_JSON
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "cacheKey": cache_key,
                    "response": response.model_dump(by_alias=True, mode="json"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    logger.bind(feature=feature_name, count=len(response.entries)).info(
        "Resolved widget enrich suggestions via LLM"
    )
    return response
