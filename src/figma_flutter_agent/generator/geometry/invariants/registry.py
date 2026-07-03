"""Executable conservation law registry (Program 02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
class ConservationLaw:
    """Registered conservation law with separate ``law_id`` and ``violation_codes``."""

    law_id: str
    violation_codes: tuple[str, ...]
    check_symbol: str
    stage: ConservationStage
    severity: ConservationSeverity
    owner: LawOwner
    description: str


_CONSERVATION_MODULE = "src/figma_flutter_agent/generator/geometry/invariants/conservation.py"

CONSERVATION_LAWS: tuple[ConservationLaw, ...] = (
    ConservationLaw(
        law_id="LAW-CONSERVE-MULTISET",
        violation_codes=("inv_node_multiset",),
        check_symbol="check_node_multiset_preserved",
        stage="CP2",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_node_multiset_preserved"),
        description="Node identity multiset preserved across pipeline arrow.",
    ),
    ConservationLaw(
        law_id="LAW-CONSERVE-PAINT-ORDER",
        violation_codes=("inv_stack_paint_order",),
        check_symbol="check_stack_paint_order_preserved",
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
        stage="CP2",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_graph_sync"),
        description="IR figmaId multiset matches clean tree after passes.",
    ),
    ConservationLaw(
        law_id="LAW-CP2-FLEX-PLACEMENT",
        violation_codes=("inv_flex_child_stack_placement",),
        check_symbol="check_flex_hosts_have_no_stack_placement",
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
        stage="CP1",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_style_truth"),
        description="Style fields preserved unless policy-allowed mutation recorded.",
    ),
    ConservationLaw(
        law_id="LAW-CP1-TYPE-TRUTH",
        violation_codes=("inv_type_truth",),
        check_symbol="check_type_truth",
        stage="CP1",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_type_truth"),
        description="Node types preserved unless legacy semantic policy allows change.",
    ),
    ConservationLaw(
        law_id="LAW-CP1-PLACEMENT-TRUTH",
        violation_codes=("inv_geometry_truth",),
        check_symbol="check_placement_truth_preserved",
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
        stage="post_classify",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_clean_tree_unchanged"),
        description="Clean tree facts unchanged during classification.",
    ),
    ConservationLaw(
        law_id="LAW-CP2-IR-KIND-STABLE",
        violation_codes=("inv_ir_kind",),
        check_symbol="check_ir_kind_preserved",
        stage="post_classify",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_ir_kind_preserved"),
        description="IR widget kinds stable outside classification scope.",
    ),
    ConservationLaw(
        law_id="LAW-OMISSION-PERMIT",
        violation_codes=("inv_omission_unpermitted",),
        check_symbol="check_omission_permits",
        stage="CP2",
        severity="block",
        owner=LawOwner(module=_CONSERVATION_MODULE, symbol="check_omission_permits"),
        description="Legitimate node omissions require typed OmissionReason permits.",
    ),
    ConservationLaw(
        law_id="LAW-PASS-CONTRACT",
        violation_codes=(),
        check_symbol="validate_pass_mutates",
        stage="CP2",
        severity="block",
        owner=LawOwner(
            module="src/figma_flutter_agent/generator/ir/passes/contract.py",
            symbol="validate_pass_mutates",
        ),
        description="IR passes mutate only declared contract fields.",
    ),
)


def laws_for_stage(stage: ConservationStage) -> tuple[ConservationLaw, ...]:
    """Return conservation laws registered for ``stage``."""
    return tuple(law for law in CONSERVATION_LAWS if law.stage == stage)


def law_by_id(law_id: str) -> ConservationLaw | None:
    """Lookup a conservation law by ``law_id``."""
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
