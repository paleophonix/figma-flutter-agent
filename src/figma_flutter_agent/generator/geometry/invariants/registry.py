"""Executable conservation law registry (Program 02)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    PlacementSnapshot,
    StyleSnapshot,
    check_clean_tree_unchanged,
    check_flex_hosts_have_no_stack_placement,
    check_graph_sync,
    check_ir_classification_scope,
    check_ir_kind_preserved,
    check_node_multiset_preserved,
    check_omission_permits,
    check_placement_truth_preserved,
    check_stack_paint_order_preserved,
    check_style_truth,
    check_type_truth,
)
from figma_flutter_agent.generator.geometry.invariants.models import (
    GeometryInvariantViolation,
    geometry_violation,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, ScreenIr

ConservationStage = Literal[
    "CP0",
    "CP0b",
    "CP1",
    "CP2",
    "post_classify",
]
ConservationSeverity = Literal["block", "warn"]


@dataclass(frozen=True, slots=True)
class LawOwner:
    """Owning module and symbol for a conservation check."""

    module: str
    symbol: str


@dataclass(frozen=True, slots=True)
class ConservationLawContext:
    """Inputs for one conservation-law execution at a pipeline checkpoint."""

    baseline_clean: CleanDesignTreeNode
    current_clean: CleanDesignTreeNode
    baseline_ir: ScreenIr | None = None
    current_ir: ScreenIr | None = None
    omit_ids: frozenset[str] = frozenset()
    omission_permits: dict[str, str] | None = None
    style_baseline: dict[str, StyleSnapshot] | None = None
    type_baseline: dict[str, NodeType] | None = None
    allowed_style_mutations: dict[tuple[str, str], str] | None = None
    type_allowed_mutations: dict[tuple[str, str], str] | None = None
    placement_baseline: dict[str, PlacementSnapshot] | None = None


ConservationCheckFn = Callable[
    [ConservationLawContext],
    list[GeometryInvariantViolation],
]


@dataclass(frozen=True, slots=True)
class ConservationLaw:
    """Registered conservation law with executable ``check_fn``."""

    law_id: str
    violation_codes: tuple[str, ...]
    check_symbol: str
    check_fn: ConservationCheckFn
    stage: ConservationStage
    severity: ConservationSeverity
    owner: LawOwner
    description: str
    executable_at_checkpoint: bool = True


_CONSERVATION_MODULE = "src/figma_flutter_agent/generator/geometry/invariants/conservation.py"


def _cp2_omission_permit_check(
    ctx: ConservationLawContext,
) -> list[GeometryInvariantViolation]:
    return check_omission_permits(
        ctx.omit_ids,
        permitted=ctx.omission_permits or {},
    )


def _cp2_multiset_check(ctx: ConservationLawContext) -> list[GeometryInvariantViolation]:
    return check_node_multiset_preserved(
        ctx.baseline_clean,
        ctx.current_clean,
        omit_ids=ctx.omit_ids,
    )


def _cp2_paint_order_check(ctx: ConservationLawContext) -> list[GeometryInvariantViolation]:
    return check_stack_paint_order_preserved(ctx.baseline_clean, ctx.current_clean)


def _cp2_graph_sync_check(ctx: ConservationLawContext) -> list[GeometryInvariantViolation]:
    if ctx.current_ir is None:
        return []
    return check_graph_sync(ctx.current_ir, ctx.current_clean)


def _cp2_flex_placement_check(ctx: ConservationLawContext) -> list[GeometryInvariantViolation]:
    return check_flex_hosts_have_no_stack_placement(ctx.current_clean)


def _cp1_style_truth_check(ctx: ConservationLawContext) -> list[GeometryInvariantViolation]:
    if ctx.style_baseline is None:
        return []
    return check_style_truth(
        ctx.style_baseline,
        ctx.current_clean,
        allowed_mutations=ctx.allowed_style_mutations or {},
    )


def _cp1_type_truth_check(ctx: ConservationLawContext) -> list[GeometryInvariantViolation]:
    if ctx.type_baseline is None or not ctx.type_baseline:
        return [
            geometry_violation(
                code="inv_type_truth_unavailable",
                node_id=ctx.current_clean.id,
                detail="type baseline missing; evidence unavailable",
            ),
        ]
    return check_type_truth(
        ctx.type_baseline,
        ctx.current_clean,
        allowed_mutations=ctx.type_allowed_mutations or {},
    )


def _cp1_placement_truth_check(ctx: ConservationLawContext) -> list[GeometryInvariantViolation]:
    if ctx.placement_baseline is None:
        return []
    return check_placement_truth_preserved(ctx.placement_baseline, ctx.current_clean)


def _post_classify_clean_tree_check(
    ctx: ConservationLawContext,
) -> list[GeometryInvariantViolation]:
    return check_clean_tree_unchanged(ctx.baseline_clean, ctx.current_clean)


def _post_classify_scope_check(
    ctx: ConservationLawContext,
) -> list[GeometryInvariantViolation]:
    if ctx.baseline_ir is None or ctx.current_ir is None:
        return []
    return check_ir_classification_scope(ctx.baseline_ir, ctx.current_ir)


def _ir_kind_preserved_check(ctx: ConservationLawContext) -> list[GeometryInvariantViolation]:
    if ctx.baseline_ir is None or ctx.current_ir is None:
        return []
    return check_ir_kind_preserved(ctx.baseline_ir, ctx.current_ir)


CONSERVATION_LAWS: tuple[ConservationLaw, ...] = (
    ConservationLaw(
        law_id="LAW-CONSERVE-MULTISET",
        violation_codes=("inv_node_multiset",),
        check_symbol="check_node_multiset_preserved",
        check_fn=_cp2_multiset_check,
        stage="CP2",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_node_multiset_preserved"),
        description="Node identity multiset preserved across pipeline arrow.",
    ),
    ConservationLaw(
        law_id="LAW-CONSERVE-PAINT-ORDER",
        violation_codes=("inv_stack_paint_order",),
        check_symbol="check_stack_paint_order_preserved",
        check_fn=_cp2_paint_order_check,
        stage="CP2",
        severity="block",
        owner=LawOwner(
            module=_CONSERVATION_MODULE,
            symbol="check_stack_paint_order_preserved",
        ),
        description="Stack child paint order preserved after IR passes.",
    ),
    ConservationLaw(
        law_id="LAW-CP2-GRAPH-SYNC",
        violation_codes=("inv_graph_sync",),
        check_symbol="check_graph_sync",
        check_fn=_cp2_graph_sync_check,
        stage="CP2",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_graph_sync"),
        description="IR figmaId multiset matches clean tree after passes.",
    ),
    ConservationLaw(
        law_id="LAW-CP2-FLEX-PLACEMENT",
        violation_codes=("inv_flex_child_stack_placement",),
        check_symbol="check_flex_hosts_have_no_stack_placement",
        check_fn=_cp2_flex_placement_check,
        stage="CP2",
        severity="block",
        owner=LawOwner(
            module=_CONSERVATION_MODULE,
            symbol="check_flex_hosts_have_no_stack_placement",
        ),
        description="Flex hosts must not retain absolute stack placement.",
    ),
    ConservationLaw(
        law_id="LAW-CP1-STYLE-TRUTH",
        violation_codes=("inv_style_truth",),
        check_symbol="check_style_truth",
        check_fn=_cp1_style_truth_check,
        stage="CP1",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_style_truth"),
        description="Style fields preserved unless policy-allowed mutation recorded.",
    ),
    ConservationLaw(
        law_id="LAW-CP1-TYPE-TRUTH",
        violation_codes=("inv_type_truth", "inv_type_truth_unavailable"),
        check_symbol="check_type_truth",
        check_fn=_cp1_type_truth_check,
        stage="CP1",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_type_truth"),
        description="Node types preserved unless legacy semantic policy allows change.",
    ),
    ConservationLaw(
        law_id="LAW-CP1-PLACEMENT-TRUTH",
        violation_codes=("inv_geometry_truth",),
        check_symbol="check_placement_truth_preserved",
        check_fn=_cp1_placement_truth_check,
        stage="CP1",
        severity="block",
        owner=LawOwner(
            module=_CONSERVATION_MODULE,
            symbol="check_placement_truth_preserved",
        ),
        description="Placement and sizing fields preserved after normalize.",
    ),
    ConservationLaw(
        law_id="LAW-CP2-CLASSIFY-SCOPE",
        violation_codes=("inv_classification_scope",),
        check_symbol="check_ir_classification_scope",
        check_fn=_post_classify_scope_check,
        stage="post_classify",
        severity="block",
        owner=LawOwner(
            module=_CONSERVATION_MODULE,
            symbol="check_ir_classification_scope",
        ),
        description="Classification may only mutate semantic IR fields.",
    ),
    ConservationLaw(
        law_id="LAW-CP2-CLEAN-TREE",
        violation_codes=("inv_classification_scope",),
        check_symbol="check_clean_tree_unchanged",
        check_fn=_post_classify_clean_tree_check,
        stage="post_classify",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_clean_tree_unchanged"),
        description="Clean tree facts unchanged during classification.",
    ),
    ConservationLaw(
        law_id="LAW-CP2-IR-KIND-STABLE",
        violation_codes=("inv_ir_kind",),
        check_symbol="check_ir_kind_preserved",
        check_fn=_ir_kind_preserved_check,
        stage="post_classify",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_ir_kind_preserved"),
        description="IR widget kinds stable outside classification scope.",
        executable_at_checkpoint=False,
    ),
    ConservationLaw(
        law_id="LAW-OMISSION-PERMIT",
        violation_codes=("inv_omission_unpermitted",),
        check_symbol="check_omission_permits",
        check_fn=_cp2_omission_permit_check,
        stage="CP2",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_omission_permits"),
        description="Legitimate node omissions require typed OmissionReason permits.",
    ),
)


@dataclass(frozen=True, slots=True)
class PassContractLawMeta:
    """Metadata for pass-contract enforcement (not run via conservation checkpoint loop)."""

    law_id: str
    check_symbol: str
    stage: ConservationStage
    severity: ConservationSeverity
    owner: LawOwner
    description: str


PASS_CONTRACT_LAW = PassContractLawMeta(
    law_id="LAW-PASS-CONTRACT",
    check_symbol="validate_pass_mutates",
    stage="CP2",
    severity="block",
    owner=LawOwner(
        module="src/figma_flutter_agent/generator/ir/passes/contract.py",
        symbol="validate_pass_mutates",
    ),
    description="IR passes mutate only declared contract fields.",
)


def laws_for_stage(stage: ConservationStage) -> tuple[ConservationLaw, ...]:
    """Return executable conservation laws registered for ``stage``."""
    return tuple(
        law
        for law in CONSERVATION_LAWS
        if law.stage == stage and law.executable_at_checkpoint
    )


def execute_conservation_laws(
    stage: ConservationStage,
    ctx: ConservationLawContext,
) -> list[GeometryInvariantViolation]:
    """Run every registered law for ``stage`` against ``ctx``."""
    violations: list[GeometryInvariantViolation] = []
    for law in laws_for_stage(stage):
        violations.extend(law.check_fn(ctx))
    return violations


def law_by_id(law_id: str) -> ConservationLaw | PassContractLawMeta | None:
    """Lookup a conservation law by ``law_id``."""
    if PASS_CONTRACT_LAW.law_id == law_id:
        return PASS_CONTRACT_LAW
    for law in CONSERVATION_LAWS:
        if law.law_id == law_id:
            return law
    return None


def all_violation_codes() -> frozenset[str]:
    """Collect every violation code referenced by registered laws."""
    codes: set[str] = set()
    for law in CONSERVATION_LAWS:
        codes.update(law.violation_codes)
    return frozenset(codes)
