"""Apply LLM naming enrichment to cluster widget specs."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.widget_extraction.gates import normalize_widget_class_name
from figma_flutter_agent.generator.widget_extraction.naming import snake_case_class_name
from figma_flutter_agent.generator.widget_extraction.props import WidgetParamBundle, WidgetParamSpec
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens
from figma_flutter_agent.schemas.reusable_candidates import WidgetEnrichResponse

_GENERIC_CLUSTER_RE = re.compile(r"^Cluster\d+Widget$")


def should_enrich_spec(spec: ClusterWidgetSpec, *, config: WidgetExtractionConfig) -> bool:
    """Return whether a cluster spec should receive LLM naming enrichment."""
    if config.enrich.enabled:
        return True
    return bool(_GENERIC_CLUSTER_RE.match(spec.class_name))


def build_enrich_entries(specs: list[ClusterWidgetSpec]) -> list[dict[str, object]]:
    """Build enrich request entries for generic or all enabled specs."""
    entries: list[dict[str, object]] = []
    for spec in specs:
        param_slots = []
        if isinstance(spec.param_bundle, WidgetParamBundle):
            param_slots = [item.name for item in spec.param_bundle.params]
        entries.append(
            {
                "clusterId": spec.cluster_id,
                "currentName": spec.class_name,
                "representativeNodeId": spec.representative.id,
                "paramSlots": param_slots,
            }
        )
    return entries


def apply_widget_enrich_response(
    specs: list[ClusterWidgetSpec],
    response: WidgetEnrichResponse,
    *,
    widget_suffix: str,
) -> list[ClusterWidgetSpec]:
    """Apply enrich response to cluster specs."""
    by_cluster = {entry.cluster_id: entry for entry in response.entries}
    enriched: list[ClusterWidgetSpec] = []
    for spec in specs:
        entry = by_cluster.get(spec.cluster_id)
        if entry is None:
            enriched.append(spec)
            continue
        class_name = normalize_widget_class_name(entry.widget_name, widget_suffix=widget_suffix)
        if class_name is None:
            enriched.append(spec)
            continue
        param_bundle = spec.param_bundle
        if isinstance(param_bundle, WidgetParamBundle) and entry.param_renames:
            params: list[WidgetParamSpec] = []
            for item in param_bundle.params:
                params.append(
                    WidgetParamSpec(
                        name=entry.param_renames.get(item.name, item.name),
                        dart_type=item.dart_type,
                        default_literal=item.default_literal,
                    )
                )
            param_bundle = WidgetParamBundle(
                params=tuple(params),
                text_literals=param_bundle.text_literals,
            )
        enriched.append(
            replace(
                spec,
                class_name=class_name,
                file_name=snake_case_class_name(class_name),
                param_bundle=param_bundle,
            )
        )
    return enriched


def enrich_cluster_specs_sync(
    specs: list[ClusterWidgetSpec],
    *,
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    config: WidgetExtractionConfig,
    settings: Any,
    project_dir: Any,
    feature_name: str,
    widget_suffix: str,
    llm_client_factory: Callable[[Any], Any] | None = None,
) -> list[ClusterWidgetSpec]:
    """Enrich cluster widget names via a synchronous LLM call."""
    targets = [spec for spec in specs if should_enrich_spec(spec, config=config)]
    if not targets or llm_client_factory is None:
        return specs

    from figma_flutter_agent.llm.enrich_clusters import resolve_widget_enrich_sync

    response = resolve_widget_enrich_sync(
        clean_tree,
        tokens,
        entries=build_enrich_entries(targets),
        config=config,
        settings=settings,
        project_dir=project_dir,
        feature_name=feature_name,
        widget_suffix=widget_suffix,
        llm_client_factory=llm_client_factory,
    )
    if response is None:
        return specs
    return apply_widget_enrich_response(specs, response, widget_suffix=widget_suffix)


async def enrich_cluster_specs(
    specs: list[ClusterWidgetSpec],
    *,
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    config: WidgetExtractionConfig,
    settings: Any,
    project_dir: Any,
    feature_name: str,
    widget_suffix: str,
    llm_client_factory: Callable[[Any], Any] | None = None,
) -> list[ClusterWidgetSpec]:
    """Enrich cluster widget names via LLM when enabled or names are generic."""
    targets = [spec for spec in specs if should_enrich_spec(spec, config=config)]
    if not targets:
        return specs
    if llm_client_factory is None:
        return specs

    from figma_flutter_agent.llm.enrich_clusters import resolve_widget_enrich

    response = await resolve_widget_enrich(
        clean_tree,
        tokens,
        entries=build_enrich_entries(targets),
        config=config,
        settings=settings,
        project_dir=project_dir,
        feature_name=feature_name,
        widget_suffix=widget_suffix,
        llm_client_factory=llm_client_factory,
    )
    if response is None:
        return specs
    return apply_widget_enrich_response(specs, response, widget_suffix=widget_suffix)
