"""Collect real cluster call-sites from clean trees (Program 04 P0-3)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.generator.extraction.definition_key import (
    DefinitionKey,
    topology_variant_for_spec,
)
from figma_flutter_agent.generator.extraction.emit_eligibility import (
    external_cluster_delegate_eligible,
)
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


def _key_for_spec(spec: ClusterWidgetSpec) -> DefinitionKey:
    return DefinitionKey.from_spec(spec, topology_variant=topology_variant_for_spec(spec))


def _index_specs_by_class_name(
    specs: list[ClusterWidgetSpec],
) -> tuple[dict[str, list[ClusterWidgetSpec]], tuple[tuple[str, str], ...]]:
    by_name: dict[str, list[ClusterWidgetSpec]] = defaultdict(list)
    for spec in specs:
        by_name[spec.class_name].append(spec)
    diagnostics = tuple(
        ("duplicate_class_definition", f"Class {name!r} maps to {len(items)} definitions")
        for name, items in sorted(by_name.items())
        if len(items) > 1
    )
    return by_name, diagnostics


def _resolve_repetition(
    node: CleanDesignTreeNode,
    candidates: list[ClusterWidgetSpec],
) -> CallsiteResolution:
    """Resolve structural repetition call-site by topology match."""
    if len(candidates) == 1:
        key = _key_for_spec(candidates[0])
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
    keys = tuple(_key_for_spec(spec) for spec in matches)
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
    specs_by_class_name: dict[str, list[ClusterWidgetSpec]],
    *,
    source_kind: ClusterSourceKind,
) -> CallsiteResolution:
    """Resolve annotation / inference call-site via ``extracted_widget_ref``."""
    ref = (node.extracted_widget_ref or "").strip()
    candidates = specs_by_class_name.get(ref, [])
    if not candidates:
        return CallsiteResolution(
            callsite_id=node.id,
            candidates=(),
            selected=None,
            evidence=f"unknown_extracted_ref:{ref}",
            status="unresolved",
            source_kind=source_kind,
        )
    keys = tuple(_key_for_spec(spec) for spec in candidates)
    if len(candidates) == 1:
        return CallsiteResolution(
            callsite_id=node.id,
            candidates=keys,
            selected=keys[0],
            evidence=f"extracted_widget_ref:{ref}",
            status="unique",
            source_kind=source_kind,
        )
    return CallsiteResolution(
        callsite_id=node.id,
        candidates=keys,
        selected=None,
        evidence=f"ambiguous_extracted_widget_ref:{ref}",
        status="ambiguous",
        source_kind=source_kind,
    )


def _resolve_component_family(
    node: CleanDesignTreeNode,
    candidates: list[ClusterWidgetSpec],
) -> CallsiteResolution:
    """Resolve component-family call-site (cluster id from component identity)."""
    base = _resolve_repetition(node, candidates)
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
    specs_by_class_name: dict[str, list[ClusterWidgetSpec]],
) -> CallsiteResolution | None:
    """Resolve one emit-authority node to a definition key."""
    ref = (node.extracted_widget_ref or "").strip()
    if ref:
        kind: ClusterSourceKind = "annotation"
        for spec in specs_by_class_name.get(ref, []):
            if spec.source_kind in {"annotation", "inference"}:
                kind = spec.source_kind
                break
        return _resolve_extracted_ref(node, specs_by_class_name, source_kind=kind)
    cluster_id = node.cluster_id or node.shape_cluster_id
    if not cluster_id:
        return None
    candidates = specs_by_cluster.get(cluster_id, [])
    if not candidates:
        return None
    kinds = {spec.source_kind for spec in candidates}
    if "component_family" in kinds:
        return _resolve_component_family(node, candidates)
    source_kind: ClusterSourceKind = "shape" if node.shape_cluster_id else "repetition"
    resolution = _resolve_repetition(node, candidates)
    if resolution.source_kind == "repetition" and source_kind == "shape":
        return CallsiteResolution(
            callsite_id=resolution.callsite_id,
            candidates=resolution.candidates,
            selected=resolution.selected,
            evidence=resolution.evidence,
            status=resolution.status,
            source_kind="shape",
        )
    return resolution


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
) -> CallsiteCollectResult:
    """Collect external and dependency call-site maps with structured resolution."""
    specs_by_cluster: dict[str, list[ClusterWidgetSpec]] = defaultdict(list)
    specs_by_class_name, class_diag = _index_specs_by_class_name(specs)
    for spec in specs:
        specs_by_cluster[spec.cluster_id].append(spec)

    external_events: list[tuple[str, DefinitionKey, ClusterSourceKind]] = []
    dependency_events: list[tuple[str, DefinitionKey, ClusterSourceKind]] = []
    resolutions: list[CallsiteResolution] = []
    diagnostics: list[tuple[str, str]] = list(class_diag)

    def record_emit_node(node: CleanDesignTreeNode, *, external: bool) -> None:
        if external and not external_cluster_delegate_eligible(node):
            return
        resolution = _resolve_emit_node(
            node,
            specs_by_cluster=specs_by_cluster,
            specs_by_class_name=specs_by_class_name,
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
