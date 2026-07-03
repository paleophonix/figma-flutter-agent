"""Cluster extraction bijection plan and validation (Program 04 P0-3)."""

from __future__ import annotations

from dataclasses import dataclass, field

from figma_flutter_agent.errors import ExtractionBijectionError
from figma_flutter_agent.generator.extraction.definition_key import DefinitionKey
from figma_flutter_agent.generator.extraction.dependencies import (
    build_definition_dependency_map,
    find_dependency_cycles,
)
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec


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
        """Build plan from cluster widget specs."""
        topo = topology_by_cluster or {}
        definitions: list[DefinitionKey] = []
        definition_to_class: dict[DefinitionKey, str] = {}
        callsite_to_definition: dict[str, DefinitionKey] = {}
        for spec in specs:
            variant = topo.get(spec.cluster_id, "default")
            key = DefinitionKey.from_spec(spec, topology_variant=variant)
            definitions.append(key)
            definition_to_class[key] = spec.class_name
            callsite = spec.representative.id if spec.representative else spec.cluster_id
            callsite_to_definition[callsite] = key
        dep_map = build_definition_dependency_map(specs, topology_by_cluster=topo)
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


def validate_extraction_bijection_shadow(plan: ClusterExtractionPlan) -> BijectionShadowReport:
    """Shadow bijection checks — diagnostics only until 04-P0-3b."""
    diagnostics: list[BijectionDiagnostic] = []
    seen_definitions: set[DefinitionKey] = set()
    for callsite, definition in plan.callsite_to_definition.items():
        if definition in seen_definitions:
            diagnostics.append(
                BijectionDiagnostic(
                    code="duplicate_definition",
                    message=f"Multiple callsites map to definition {definition!r}",
                    cluster_id=definition.cluster_id,
                ),
            )
        seen_definitions.add(definition)
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
    if len(plan.definitions) > len(plan.callsite_to_definition):
        diagnostics.append(
            BijectionDiagnostic(
                code="duplicate_callsite",
                message="Multiple definitions share the same callsite id",
                cluster_id=None,
            ),
        )
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
    """Blocking bijection gate (04-P0-3b) — requires M3 authority flag."""
    from figma_flutter_agent.compiler.m3_authority import require_m3_authority

    require_m3_authority("extraction_bijection")
    report = validate_extraction_bijection_shadow(plan)
    if report.ok:
        return
    first = report.diagnostics[0]
    raise ExtractionBijectionError(f"{first.code}: {first.message}")
