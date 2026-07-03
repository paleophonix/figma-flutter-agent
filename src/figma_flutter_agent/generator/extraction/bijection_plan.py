"""Cluster extraction bijection plan and validation (Program 04 P0-3)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from figma_flutter_agent.errors import ExtractionBijectionError
from figma_flutter_agent.generator.extraction.callsite_index import collect_cluster_callsites
from figma_flutter_agent.generator.extraction.definition_key import DefinitionKey
from figma_flutter_agent.generator.extraction.dependencies import (
    build_definition_dependency_map,
    find_dependency_cycles,
)
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode


@dataclass(frozen=True, slots=True)
class ClusterExtractionPlan:
    """Early extraction bijection table: callsite → definition → class → dependencies."""

    definitions: tuple[DefinitionKey, ...]
    callsite_to_definition: dict[str, DefinitionKey]
    definition_to_class: dict[DefinitionKey, str]
    dependencies: dict[DefinitionKey, frozenset[DefinitionKey]]

    @classmethod
    def from_specs(
        cls,
        specs: list[ClusterWidgetSpec],
        *,
        topology_by_cluster: dict[str, str] | None = None,
    ) -> ClusterExtractionPlan:
        """Build plan from specs only (tests); prefers ``from_specs_and_trees`` in production."""
        return cls.from_specs_and_trees(specs, [], topology_by_cluster=topology_by_cluster)

    @classmethod
    def from_specs_and_trees(
        cls,
        specs: list[ClusterWidgetSpec],
        clean_trees: list[CleanDesignTreeNode],
        *,
        topology_by_cluster: dict[str, str] | None = None,
    ) -> ClusterExtractionPlan:
        """Build plan from specs and real clean-tree call-site nodes."""
        topo = topology_by_cluster or {}
        definitions: list[DefinitionKey] = []
        definition_to_class: dict[DefinitionKey, str] = {}
        for spec in specs:
            variant = topo.get(spec.cluster_id, "default")
            key = DefinitionKey.from_spec(spec, topology_variant=variant)
            definitions.append(key)
            definition_to_class[key] = spec.class_name
        callsite_to_definition = collect_cluster_callsites(
            specs,
            clean_trees,
            topology_by_cluster=topo,
        )
        dep_map = build_definition_dependency_map(
            specs,
            callsite_to_definition=callsite_to_definition,
            topology_by_cluster=topo,
        )
        return cls(
            definitions=tuple(definitions),
            callsite_to_definition=callsite_to_definition,
            definition_to_class=definition_to_class,
            dependencies=dep_map,
        )


@dataclass(frozen=True, slots=True)
class BijectionDiagnostic:
    """Non-blocking shadow bijection finding."""

    code: str
    message: str
    cluster_id: str | None = None


@dataclass
class BijectionShadowReport:
    """Shadow validation report (diagnostics only pre-M2)."""

    ok: bool
    diagnostics: list[BijectionDiagnostic] = field(default_factory=list)


def _definition_to_callsites(plan: ClusterExtractionPlan) -> dict[DefinitionKey, list[str]]:
    reverse: dict[DefinitionKey, list[str]] = defaultdict(list)
    for callsite, definition in plan.callsite_to_definition.items():
        reverse[definition].append(callsite)
    return reverse


def validate_extraction_bijection_shadow(plan: ClusterExtractionPlan) -> BijectionShadowReport:
    """Shadow bijection checks — diagnostics only until 04-P0-3b."""
    diagnostics: list[BijectionDiagnostic] = []
    reverse = _definition_to_callsites(plan)

    for callsite, definition in plan.callsite_to_definition.items():
        class_name = plan.definition_to_class.get(definition)
        if not class_name:
            diagnostics.append(
                BijectionDiagnostic(
                    code="missing_class",
                    message=f"Definition {definition!r} has no class mapping",
                    cluster_id=definition.cluster_id,
                ),
            )
        if not callsite:
            diagnostics.append(
                BijectionDiagnostic(
                    code="empty_callsite",
                    message="Empty callsite id in bijection plan",
                    cluster_id=definition.cluster_id,
                ),
            )

    for definition in plan.definitions:
        if definition not in plan.definition_to_class:
            diagnostics.append(
                BijectionDiagnostic(
                    code="orphan_definition",
                    message=f"Definition {definition!r} not referenced by class map",
                    cluster_id=definition.cluster_id,
                ),
            )
            continue
        if not reverse.get(definition):
            diagnostics.append(
                BijectionDiagnostic(
                    code="orphan_definition",
                    message=f"Definition {definition!r} has no call-sites",
                    cluster_id=definition.cluster_id,
                ),
            )

    seen_callsites: set[str] = set()
    for callsite in plan.callsite_to_definition:
        if callsite in seen_callsites:
            diagnostics.append(
                BijectionDiagnostic(
                    code="duplicate_callsite",
                    message=f"Duplicate callsite id {callsite!r} in bijection plan",
                    cluster_id=None,
                ),
            )
        seen_callsites.add(callsite)

    cycles = find_dependency_cycles(plan.dependencies)
    for cycle in cycles:
        labels = " -> ".join(item.cluster_id for item in cycle)
        diagnostics.append(
            BijectionDiagnostic(
                code="delegate_dependency_cycle",
                message=f"Delegate dependency cycle: {labels}",
                cluster_id=cycle[0].cluster_id if cycle else None,
            ),
        )
    return BijectionShadowReport(ok=not diagnostics, diagnostics=diagnostics)


def enforce_extraction_bijection(plan: ClusterExtractionPlan) -> None:
    """Blocking bijection gate (04-P0-3b) — requires M3 bijection ENFORCE mode."""
    from figma_flutter_agent.compiler.m3_authority import require_m3_authority

    require_m3_authority("extraction_bijection")
    report = validate_extraction_bijection_shadow(plan)
    if report.ok:
        return
    first = report.diagnostics[0]
    raise ExtractionBijectionError(f"{first.code}: {first.message}")
