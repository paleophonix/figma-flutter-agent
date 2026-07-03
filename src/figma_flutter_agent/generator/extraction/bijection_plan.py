"""Cluster extraction bijection plan and validation (Program 04 P0-3)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from figma_flutter_agent.compiler.m3_authority import require_m3_authority
from figma_flutter_agent.compiler.m3_policy import DEFAULT_M3_POLICY, M3Policy
from figma_flutter_agent.errors import ExtractionBijectionError
from figma_flutter_agent.generator.extraction.callsite_index import collect_cluster_callsites
from figma_flutter_agent.generator.extraction.definition_key import (
    DefinitionKey,
    topology_variant_for_spec,
)
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
    collect_diagnostics: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_specs(cls, specs: list[ClusterWidgetSpec]) -> ClusterExtractionPlan:
        """Build plan from specs only (tests); prefers ``from_specs_and_trees`` in production."""
        return cls.from_specs_and_trees(specs, [])

    @classmethod
    def from_specs_and_trees(
        cls,
        specs: list[ClusterWidgetSpec],
        clean_trees: list[CleanDesignTreeNode],
    ) -> ClusterExtractionPlan:
        """Build plan from specs and real clean-tree call-site nodes."""
        definitions: list[DefinitionKey] = []
        definition_to_class: dict[DefinitionKey, str] = {}
        for spec in specs:
            key = DefinitionKey.from_spec(
                spec,
                topology_variant=topology_variant_for_spec(spec),
            )
            definitions.append(key)
            definition_to_class[key] = spec.class_name
        collected = collect_cluster_callsites(specs, clean_trees)
        dep_map = build_definition_dependency_map(
            specs,
            callsite_to_definition=collected.dependency_callsites,
        )
        return cls(
            definitions=tuple(definitions),
            callsite_to_definition=collected.external_callsites,
            definition_to_class=definition_to_class,
            dependencies=dep_map,
            collect_diagnostics=collected.diagnostics,
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

    for code, message in plan.collect_diagnostics:
        diagnostics.append(BijectionDiagnostic(code=code, message=message))

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
                    message=f"Definition {definition!r} has no external call-sites",
                    cluster_id=definition.cluster_id,
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


def enforce_extraction_bijection(
    plan: ClusterExtractionPlan,
    *,
    policy: M3Policy = DEFAULT_M3_POLICY,
) -> None:
    """Blocking bijection gate (04-P0-3b) — requires M3 bijection ENFORCE mode."""
    require_m3_authority("extraction_bijection", policy)
    report = validate_extraction_bijection_shadow(plan)
    if report.ok:
        return
    first = report.diagnostics[0]
    raise ExtractionBijectionError(f"{first.code}: {first.message}")
