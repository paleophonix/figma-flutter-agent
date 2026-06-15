"""Conservation checkpoint orchestration (parser + IR layers)."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    StyleSnapshot,
    allowed_style_mutations_from_provenance,
    capture_placement_baseline,
    capture_style_baseline,
    check_graph_sync,
    check_node_multiset_preserved,
    check_placement_truth_preserved,
    check_stack_paint_order_preserved,
    check_style_truth,
    check_type_truth,
    conservation_node_multiset,
)
from figma_flutter_agent.generator.geometry.invariants.models import GeometryInvariantViolation
from figma_flutter_agent.generator.geometry.invariants.reporting import (
    raise_on_hard_geometry_violations,
)
from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, ScreenIr

_conservation_session: ContextVar[ConservationSession | None] = ContextVar(
    "conservation_session",
    default=None,
)


@dataclass
class ConservationSession:
    """Per-run conservation baselines captured during parse and normalize."""

    style_baseline: dict[str, StyleSnapshot] = field(default_factory=dict)
    type_baseline: dict[str, NodeType] = field(default_factory=dict)
    legacy_semantic_type_ids: set[str] = field(default_factory=set)
    allowed_style_mutations: dict[tuple[str, str], str] = field(default_factory=dict)
    parse_complete: bool = False


def activate_conservation_session() -> ConservationSession:
    """Install a conservation session for the current context."""
    session = ConservationSession()
    _conservation_session.set(session)
    return session


def get_conservation_session() -> ConservationSession | None:
    """Return the active conservation session, if any."""
    return _conservation_session.get()


def clear_conservation_session() -> None:
    """Remove the active conservation session."""
    _conservation_session.set(None)


def set_parse_style_baseline(tree: CleanDesignTreeNode) -> None:
    """Capture post-parse style baseline at end of ``build_clean_tree``."""
    session = get_conservation_session()
    if session is None:
        session = activate_conservation_session()
    session.style_baseline = capture_style_baseline(tree)
    session.parse_complete = True


def record_allowed_style_mutation(
    *,
    node_id: str,
    field: str,
    policy: str,
) -> None:
    """Register a policy-allowed style mutation before provenance recorder is active."""
    session = get_conservation_session()
    if session is None:
        return
    session.allowed_style_mutations[(node_id, field)] = policy


def validate_multiset_checkpoint(
    baseline: CleanDesignTreeNode,
    current: CleanDesignTreeNode,
    *,
    context: str,
    omit_ids: frozenset[str] | None = None,
    allowed_removed_ids: frozenset[str] | None = None,
) -> list[GeometryInvariantViolation]:
    """Validate multiset preservation and raise on hard violations."""
    violations = check_node_multiset_preserved(
        baseline,
        current,
        omit_ids=omit_ids,
        allowed_removed_ids=allowed_removed_ids,
    )
    raise_on_hard_geometry_violations(violations, context=context)
    return violations


def run_cp0_parse_dedup(
    tree: CleanDesignTreeNode,
    *,
    prune_fn: Callable[[], None],
) -> None:
    """CP0: validate dedup does not drop node ids (E0.1 TM-1 guard)."""
    from figma_flutter_agent.debug.provenance import get_provenance_recorder

    baseline = deep_copy_clean_tree(tree)
    pre_counts = conservation_node_multiset(baseline)
    prune_fn()
    post_counts = conservation_node_multiset(tree)
    recorder = get_provenance_recorder()
    if recorder is not None:
        recorder.note_checkpoint("CP0_parse")
        for node_id, before in pre_counts.items():
            after = post_counts.get(node_id, 0)
            if before != after:
                recorder.record_mutation(
                    checkpoint="CP0_parse",
                    transform="dedup_prune",
                    node_id=node_id,
                    field="multiset_count",
                    old=before,
                    new=after,
                )
    validate_multiset_checkpoint(baseline, tree, context="CP0_parse")


def run_cp0b_reprune(
    tree: CleanDesignTreeNode,
    *,
    prune_fn: Callable[[], None],
    allowed_removed_ids: frozenset[str] | None = None,
) -> None:
    """CP0b: validate repeated prune is multiset-idempotent."""
    from figma_flutter_agent.debug.provenance import get_provenance_recorder

    baseline = deep_copy_clean_tree(tree)
    prune_fn()
    recorder = get_provenance_recorder()
    if recorder is not None:
        recorder.note_checkpoint("CP0b_reprune")
    validate_multiset_checkpoint(
        baseline,
        tree,
        context="CP0b_reprune",
        allowed_removed_ids=allowed_removed_ids,
    )


def run_cp1_normalize(
    tree: CleanDesignTreeNode,
    *,
    transform_fn: Callable[[CleanDesignTreeNode], CleanDesignTreeNode],
    check_placement_truth: bool = False,
) -> CleanDesignTreeNode:
    """CP1: validate normalize/reconcile preserves node multiset."""
    from figma_flutter_agent.debug.provenance import get_provenance_recorder

    baseline = deep_copy_clean_tree(tree)
    result = transform_fn(tree)
    recorder = get_provenance_recorder()
    if recorder is not None:
        recorder.note_checkpoint("CP1_normalize")
    validate_multiset_checkpoint(baseline, result, context="CP1_normalize")
    session = get_conservation_session()
    if session and session.style_baseline:
        allowed: dict[tuple[str, str], str] = dict(session.allowed_style_mutations)
        if recorder is not None:
            allowed.update(allowed_style_mutations_from_provenance(recorder.mutations))
        style_violations = check_style_truth(
            session.style_baseline,
            result,
            allowed_mutations=allowed,
        )
        raise_on_hard_geometry_violations(style_violations, context="CP1_style_truth")
    if session and session.type_baseline:
        type_allowed: dict[tuple[str, str], str] = {}
        if recorder is not None:
            for item in recorder.mutations:
                if item.policy == "legacy_semantic_type" and item.field == "type":
                    type_allowed[(item.node_id, "type")] = item.policy
        type_violations = check_type_truth(
            session.type_baseline,
            result,
            allowed_mutations=type_allowed,
        )
        raise_on_hard_geometry_violations(type_violations, context="CP1_type_truth")
    if check_placement_truth:
        placement_baseline = capture_placement_baseline(baseline)
        placement_violations = check_placement_truth_preserved(placement_baseline, result)
        raise_on_hard_geometry_violations(
            placement_violations,
            context="CP1_placement_truth",
        )
    return result


def run_cp_post_classify(
    baseline_clean: CleanDesignTreeNode,
    baseline_ir: ScreenIr,
    result_clean: CleanDesignTreeNode,
    result_ir: ScreenIr,
) -> None:
    """CP2b: classification must not mutate clean-tree or non-semantic IR fields."""
    from figma_flutter_agent.debug.provenance import get_provenance_recorder
    from figma_flutter_agent.generator.geometry.invariants.conservation import (
        check_clean_tree_unchanged,
        check_ir_classification_scope,
    )

    recorder = get_provenance_recorder()
    if recorder is not None:
        recorder.note_checkpoint("CP2_post_classify")
    violations: list[GeometryInvariantViolation] = []
    violations.extend(check_clean_tree_unchanged(baseline_clean, result_clean))
    violations.extend(check_ir_classification_scope(baseline_ir, result_ir))
    raise_on_hard_geometry_violations(violations, context="CP2_post_classify")


def run_cp2_ir_passes(
    baseline_clean: CleanDesignTreeNode,
    baseline_ir: ScreenIr,
    result_clean: CleanDesignTreeNode,
    result_ir: ScreenIr,
) -> None:
    """CP2: validate IR pass output preserves conservation laws."""
    from figma_flutter_agent.debug.provenance import get_provenance_recorder

    recorder = get_provenance_recorder()
    if recorder is not None:
        recorder.note_checkpoint("CP2_ir_passes")
    omit_ids = frozenset(baseline_ir.omit_figma_ids or [])
    violations: list[GeometryInvariantViolation] = []
    violations.extend(
        check_node_multiset_preserved(baseline_clean, result_clean, omit_ids=omit_ids),
    )
    violations.extend(check_stack_paint_order_preserved(baseline_clean, result_clean))
    violations.extend(check_graph_sync(result_ir, result_clean))
    raise_on_hard_geometry_violations(violations, context="CP2_ir_passes")
