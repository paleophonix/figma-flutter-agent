"""Unified widget spec collection across extraction sources."""

from __future__ import annotations

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.widget_extraction.eligibility import (
    is_eligible_extraction_candidate,
)
from figma_flutter_agent.generator.widget_extraction.naming import (
    fallback_class_name,
    snake_case_class_name,
)
from figma_flutter_agent.generator.widget_extraction.policy import (
    effective_min_count,
    resolve_widget_extraction_sources,
)
from figma_flutter_agent.generator.widget_extraction.props import diff_props
from figma_flutter_agent.generator.widget_extraction.semantic import (
    InferenceCandidate,
    discover_semantic_candidates,
)
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.parser.annotations.widget_marker import (
    apply_widget_layer_annotations,
    collect_annotated_widget_nodes,
    parse_widget_annotation,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode


def collect_widget_specs(
    root: CleanDesignTreeNode,
    cluster_summary: dict[str, int],
    *,
    config: WidgetExtractionConfig,
    widget_suffix: str = "Widget",
    legacy_enforce: bool = True,
    legacy_min_count: int = 2,
    llm_candidates: list | None = None,
) -> list[ClusterWidgetSpec]:
    """Collect widget specs from annotation, repetition, and gated inference sources."""
    sources = resolve_widget_extraction_sources(config)
    if not legacy_enforce or config.policy == "off":
        if config.policy == "off":
            return []
    min_count = effective_min_count(config, legacy_min_count=legacy_min_count)
    specs: list[ClusterWidgetSpec] = []
    existing_cluster_ids: set[str] = set()
    existing_class_names: set[str] = set()
    claimed_component_ids: set[str] = set()
    claimed_node_ids: set[str] = set()

    if sources.annotation:
        apply_widget_layer_annotations(
            root,
            prefixes=config.annotation_prefixes,
            widget_suffix=widget_suffix,
        )
        specs.extend(
            _collect_annotated_widget_specs(
                root,
                prefixes=config.annotation_prefixes,
                widget_suffix=widget_suffix,
                existing_cluster_ids=existing_cluster_ids,
                existing_class_names=existing_class_names,
                claimed_component_ids=claimed_component_ids,
                claimed_node_ids=claimed_node_ids,
            )
        )

    if sources.annotation and config.extract_figma_components_single_use:
        from figma_flutter_agent.generator.widget_extractor import (
            _collect_component_family_widget_specs,
        )

        specs.extend(
            _collect_component_family_widget_specs(
                root,
                min_count=1,
                widget_suffix=widget_suffix,
                existing_cluster_ids=existing_cluster_ids,
                existing_class_names=existing_class_names,
                claimed_component_ids=claimed_component_ids,
                allow_single_use=True,
            )
        )

    if sources.repetition:
        from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs

        shape_summary: dict[str, int] | None = None
        shape_members: dict[str, list[CleanDesignTreeNode]] = {}
        if config.parameterize_text:
            from figma_flutter_agent.generator.widget_extraction.shape import (
                assign_shape_clusters,
                index_shape_clusters,
            )

            shape_summary = assign_shape_clusters(root, min_count=min_count)
            _, shape_members = index_shape_clusters(root, min_count=min_count)

        repetition_specs = collect_cluster_widget_specs(
            root,
            cluster_summary,
            min_count=min_count,
            widget_suffix=widget_suffix,
            shape_cluster_summary=shape_summary,
        )
        shape_specs = _collect_shape_widget_specs(
            shape_members,
            widget_suffix=widget_suffix,
            existing_cluster_ids=existing_cluster_ids,
            existing_class_names=existing_class_names,
        )
        shape_cluster_ids = {spec.cluster_id for spec in shape_specs}
        for spec in shape_specs:
            specs.append(spec)
            existing_cluster_ids.add(spec.cluster_id)
            existing_class_names.add(spec.class_name)
        for spec in repetition_specs:
            if spec.cluster_id in shape_cluster_ids:
                continue
            if spec.class_name in existing_class_names:
                continue
            component_id = _component_id_for_node(spec.representative)
            if component_id and component_id in claimed_component_ids:
                continue
            specs.append(spec)
            existing_cluster_ids.add(spec.cluster_id)
            existing_class_names.add(spec.class_name)
            if component_id:
                claimed_component_ids.add(component_id)

    if sources.inference:
        from figma_flutter_agent.schemas.reusable_candidates import ReusableWidgetCandidate

        candidates = llm_candidates or []
        typed_candidates = [
            item if isinstance(item, ReusableWidgetCandidate) else ReusableWidgetCandidate.model_validate(item)
            for item in candidates
        ]
        for inference in discover_semantic_candidates(
            root,
            config=config,
            llm_candidates=typed_candidates or None,
            widget_suffix=widget_suffix,
            legacy_min_count=min_count,
            claimed_class_names=existing_class_names,
            claimed_node_ids=claimed_node_ids,
        ):
            if inference.node.id in claimed_node_ids:
                continue
            class_name = inference.widget_name
            if class_name in existing_class_names:
                continue
            cluster_id = f"semantic_{inference.node.id.replace(':', '_')}"
            param_bundle = _param_bundle_for_inference(inference, root, min_count=min_count)
            specs.append(
                ClusterWidgetSpec(
                    cluster_id=cluster_id,
                    class_name=class_name,
                    file_name=snake_case_class_name(class_name),
                    representative=inference.node,
                    param_bundle=param_bundle,
                )
            )
            existing_cluster_ids.add(cluster_id)
            existing_class_names.add(class_name)
            claimed_node_ids.add(inference.node.id)

    return sorted(specs, key=lambda item: (item.cluster_id, item.class_name))


def _collect_shape_widget_specs(
    shape_members: dict[str, list[CleanDesignTreeNode]],
    *,
    widget_suffix: str,
    existing_cluster_ids: set[str],
    existing_class_names: set[str],
) -> list[ClusterWidgetSpec]:
    from figma_flutter_agent.generator.layout.common import to_snake_case
    from figma_flutter_agent.generator.widget_extractor import (
        _representative_score,
        _widget_class_name,
    )

    specs: list[ClusterWidgetSpec] = []
    for cluster_id, members in shape_members.items():
        if cluster_id in existing_cluster_ids:
            continue
        bundle = diff_props(members)
        if bundle is None:
            continue
        representative = max(members, key=_representative_score)
        class_name = _widget_class_name(representative, cluster_id, widget_suffix)
        if class_name in existing_class_names:
            continue
        specs.append(
            ClusterWidgetSpec(
                cluster_id=cluster_id,
                class_name=class_name,
                file_name=to_snake_case(class_name),
                representative=representative,
                param_bundle=bundle,
                shape_members=tuple(members),
            )
        )
    return specs


def _collect_annotated_widget_specs(
    root: CleanDesignTreeNode,
    *,
    prefixes: list[str],
    widget_suffix: str,
    existing_cluster_ids: set[str],
    existing_class_names: set[str],
    claimed_component_ids: set[str],
    claimed_node_ids: set[str],
) -> list[ClusterWidgetSpec]:
    from figma_flutter_agent.generator.cluster_variants import component_id_for_node
    from figma_flutter_agent.generator.layout.common import to_snake_case
    from figma_flutter_agent.parser.interaction import (
        layout_fact_hosts_compact_checkbox_control,
        layout_fact_hosts_payment_selection_indicator,
        must_inline_extracted_widget_host,
    )

    specs: list[ClusterWidgetSpec] = []
    for node, class_name in collect_annotated_widget_nodes(
        root,
        prefixes=prefixes,
        widget_suffix=widget_suffix,
    ):
        if node.id in claimed_node_ids or class_name in existing_class_names:
            continue
        if (
            must_inline_extracted_widget_host(node)
            or layout_fact_hosts_compact_checkbox_control(node)
            or layout_fact_hosts_payment_selection_indicator(node)
        ):
            continue
        if not is_eligible_extraction_candidate(node) and not parse_widget_annotation(
            node.name,
            prefixes,
        ):
            continue
        node.extracted_widget_ref = class_name
        cluster_id = f"annotation_{node.id.replace(':', '_')}"
        specs.append(
            ClusterWidgetSpec(
                cluster_id=cluster_id,
                class_name=class_name,
                file_name=to_snake_case(class_name),
                representative=node,
            )
        )
        existing_cluster_ids.add(cluster_id)
        existing_class_names.add(class_name)
        claimed_node_ids.add(node.id)
        component_id = component_id_for_node(node)
        if component_id:
            claimed_component_ids.add(component_id)
    return specs


def _component_id_for_node(node: CleanDesignTreeNode) -> str | None:
    from figma_flutter_agent.generator.cluster_variants import component_id_for_node

    return component_id_for_node(node)


def _param_bundle_for_inference(
    inference: InferenceCandidate,
    root: CleanDesignTreeNode,
    *,
    min_count: int,
) -> object | None:
    """Build param bundle when inference suggests params and shape members exist."""
    if not inference.suggested_params:
        return None
    from figma_flutter_agent.generator.widget_extraction.shape import index_shape_clusters

    _, members = index_shape_clusters(root, min_count=min_count)
    for group in members.values():
        if any(node.id == inference.node.id for node in group):
            bundle = diff_props(group)
            if bundle is None:
                return None
            return _rename_param_bundle(bundle, inference.suggested_params)
    return None


def _rename_param_bundle(bundle: object, suggested_names: tuple[str, ...]) -> object:
    from figma_flutter_agent.generator.widget_extraction.props import (
        WidgetParamBundle,
        WidgetParamSpec,
    )

    if not isinstance(bundle, WidgetParamBundle):
        return bundle
    params: list[WidgetParamSpec] = []
    for index, spec in enumerate(bundle.params):
        name = suggested_names[index] if index < len(suggested_names) else spec.name
        params.append(
            WidgetParamSpec(
                name=name,
                dart_type=spec.dart_type,
                default_literal=spec.default_literal,
            )
        )
    return WidgetParamBundle(params=tuple(params), text_literals=bundle.text_literals)


def _fallback_class_name(node: CleanDesignTreeNode, widget_suffix: str) -> str:
    return fallback_class_name(node, widget_suffix)


def _snake_case(class_name: str) -> str:
    return snake_case_class_name(class_name)
