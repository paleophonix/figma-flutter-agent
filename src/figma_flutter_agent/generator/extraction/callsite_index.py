"""Collect real cluster call-sites from clean trees (Program 04 P0-3)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.generator.extraction.definition_key import DefinitionKey
from figma_flutter_agent.generator.variant_topology import compare_variant_topology
from figma_flutter_agent.generator.widget_models import ClusterSourceKind, ClusterWidgetSpec
from figma_flutter_agent.parser.tree_walk import walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode

CallsiteResolutionStatus = Literal["unique", "ambiguous", "unresolved"]


@dataclass(frozen=True, slots=True)
class CallsiteResolution:
    """Structured result of mapping one emit node to a definition key."""

    callsite_id: str
    candidates: tuple[DefinitionKey, ...]
    selected: DefinitionKey | None
    evidence: str
    status: CallsiteResolutionStatus
    source_kind: ClusterSourceKind


@dataclass(frozen=True, slots=True)
class CallsiteCollectResult:
    """External + dependency call-site maps with pre-dict collision diagnostics."""

    external_callsites: dict[str, DefinitionKey]
    dependency_callsites: dict[str, DefinitionKey]
    resolutions: tuple[CallsiteResolution, ...]
    diagnostics: tuple[tuple[str, str], ...]


def _key_for_spec(
    spec: ClusterWidgetSpec,
    *,
    topology_by_cluster: dict[str, str],
) -> DefinitionKey:
    variant = topology_by_cluster.get(spec.cluster_id, "default")
    return DefinitionKey.from_spec(spec, topology_variant=variant)


def _resolve_repetition(
    node: CleanDesignTreeNode,
    candidates: list[ClusterWidgetSpec],
    *,
    topology_by_cluster: dict[str, str],
) -> CallsiteResolution:
    """Resolve structural repetition call-site by topology match."""
    if len(candidates) == 1:
        key = _key_for_spec(candidates[0], topology_by_cluster=topology_by_cluster)
        return CallsiteResolution(
            callsite_id=node.id,
            candidates=(key,),
            selected=key,
            evidence="single_cluster_definition",
            status="unique",
            source_kind="repetition",
        )
    matches = [
        spec
        for spec in candidates
        if spec.representative is not None
        and not compare_variant_topology(spec.representative, node).should_split
    ]
    keys = tuple(_key_for_spec(spec, topology_by_cluster=topology_by_cluster) for spec in matches)
    if len(matches) == 1:
        return CallsiteResolution(
            callsite_id=node.id,
            candidates=keys,
            selected=keys[0],
            evidence="topology_unique_match",
            status="unique",
            source_kind="repetition",
        )
    if len(matches) > 1:
        return CallsiteResolution(
            callsite_id=node.id,
            candidates=keys,
            selected=None,
            evidence="topology_ambiguous",
            status="ambiguous",
            source_kind="repetition",
        )
    return CallsiteResolution(
        callsite_id=node.id,
        candidates=(),
        selected=None,
        evidence="topology_unresolved",
        status="unresolved",
        source_kind="repetition",
    )


def _resolve_extracted_ref(
    node: CleanDesignTreeNode,
    class_by_name: dict[str, ClusterWidgetSpec],
    *,
    topology_by_cluster: dict[str, str],
    source_kind: ClusterSourceKind,
) -> CallsiteResolution:
    """Resolve annotation / inference call-site via ``extracted_widget_ref``."""
    ref = (node.extracted_widget_ref or "").strip()
    spec = class_by_name.get(ref)
    if spec is None:
        return CallsiteResolution(
            callsite_id=node.id,
            candidates=(),
            selected=None,
            evidence=f"unknown_extracted_ref:{ref}",
            status="unresolved",
            source_kind=source_kind,
        )
    key = _key_for_spec(spec, topology_by_cluster=topology_by_cluster)
    return CallsiteResolution(
        callsite_id=node.id,
        candidates=(key,),
        selected=key,
        evidence=f"extracted_widget_ref:{ref}",
        status="unique",
        source_kind=source_kind,
    )


def _resolve_component_family(
    node: CleanDesignTreeNode,
    candidates: list[ClusterWidgetSpec],
    *,
    topology_by_cluster: dict[str, str],
) -> CallsiteResolution:
    """Resolve component-family call-site (cluster id from component identity)."""
    base = _resolve_repetition(node, candidates, topology_by_cluster=topology_by_cluster)
    return CallsiteResolution(
        callsite_id=base.callsite_id,
        candidates=base.candidates,
        selected=base.selected,
        evidence="component_family_cluster_id",
        status=base.status,
        source_kind="component_family",
    )


def _resolve_emit_node(
    node: CleanDesignTreeNode,
    *,
    specs_by_cluster: dict[str, list[ClusterWidgetSpec]],
    class_by_name: dict[str, ClusterWidgetSpec],
    topology_by_cluster: dict[str, str],
) -> CallsiteResolution | None:
    """Resolve one emit-authority node to a definition key."""
    ref = (node.extracted_widget_ref or "").strip()
    if ref:
        kind: ClusterSourceKind = "annotation"
        for spec in class_by_name.values():
            if spec.class_name == ref:
                kind = spec.source_kind if spec.source_kind in {"annotation", "inference"} else "annotation"
                break
        return _resolve_extracted_ref(
            node,
            class_by_name,
            topology_by_cluster=topology_by_cluster,
            source_kind=kind,
        )
    cluster_id = node.cluster_id or node.shape_cluster_id
    if not cluster_id:
        return None
    candidates = specs_by_cluster.get(cluster_id, [])
    if not candidates:
        return None
    kinds = {spec.source_kind for spec in candidates}
    if "component_family" in kinds:
        return _resolve_component_family(
            node,
            candidates,
            topology_by_cluster=topology_by_cluster,
        )
    return _resolve_repetition(
        node,
        candidates,
        topology_by_cluster=topology_by_cluster,
    )


def _materialize_events(
    events: list[tuple[str, DefinitionKey, ClusterSourceKind]],
) -> tuple[dict[str, DefinitionKey], tuple[tuple[str, str], ...]]:
    """Validate collisions before building authoritative dict."""
    mapping: dict[str, DefinitionKey] = {}
    diagnostics: list[tuple[str, str]] = []
    for callsite_id, key, _kind in events:
        if callsite_id in mapping:
            if mapping[callsite_id] == key:
                continue
            diagnostics.append(
                (
                    "callsite_key_collision",
                    f"Callsite {callsite_id!r} maps to both {mapping[callsite_id]!r} and {key!r}",
                ),
            )
            continue
        mapping[callsite_id] = key
    return mapping, tuple(diagnostics)


def collect_cluster_callsites(
    specs: list[ClusterWidgetSpec],
    clean_trees: list[CleanDesignTreeNode],
    *,
    topology_by_cluster: dict[str, str] | None = None,
) -> CallsiteCollectResult:
    """Collect external and dependency call-site maps with structured resolution."""
    topo = topology_by_cluster or {}
    specs_by_cluster: dict[str, list[ClusterWidgetSpec]] = defaultdict(list)
    class_by_name = {spec.class_name: spec for spec in specs}
    for spec in specs:
        specs_by_cluster[spec.cluster_id].append(spec)

    external_events: list[tuple[str, DefinitionKey, ClusterSourceKind]] = []
    dependency_events: list[tuple[str, DefinitionKey, ClusterSourceKind]] = []
    resolutions: list[CallsiteResolution] = []
    diagnostics: list[tuple[str, str]] = []

    for spec in specs:
        key = _key_for_spec(spec, topology_by_cluster=topo)
        for member in spec.shape_members:
            external_events.append((member.id, key, "shape"))
            dependency_events.append((member.id, key, "shape"))

    def record_emit_node(node: CleanDesignTreeNode, *, external: bool) -> None:
        resolution = _resolve_emit_node(
            node,
            specs_by_cluster=specs_by_cluster,
            class_by_name=class_by_name,
            topology_by_cluster=topo,
        )
        if resolution is None:
            return
        resolutions.append(resolution)
        if resolution.status != "unique" or resolution.selected is None:
            diagnostics.append(
                (
                    f"callsite_{resolution.status}",
                    f"{resolution.callsite_id}: {resolution.evidence}",
                ),
            )
            return
        event = (resolution.callsite_id, resolution.selected, resolution.source_kind)
        if external:
            external_events.append(event)
        dependency_events.append(event)

    for tree in clean_trees:
        walk_clean_tree(
            tree,
            lambda node: record_emit_node(node, external=True),
            phase="bijection_callsite_collect",
        )

    for spec in specs:
        if spec.representative is None:
            continue
        walk_clean_tree(
            spec.representative,
            lambda node: record_emit_node(node, external=False),
            phase="bijection_dependency_delegate_collect",
        )

    external_map, external_diag = _materialize_events(external_events)
    dependency_map, dependency_diag = _materialize_events(dependency_events)
    diagnostics.extend(external_diag)
    diagnostics.extend(dependency_diag)

    return CallsiteCollectResult(
        external_callsites=external_map,
        dependency_callsites=dependency_map,
        resolutions=tuple(resolutions),
        diagnostics=tuple(diagnostics),
    )
