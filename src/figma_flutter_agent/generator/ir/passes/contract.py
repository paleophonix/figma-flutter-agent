"""Per-pass preservation contract validation for IR layout passes."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_clean_tree_unchanged,
    check_graph_sync,
    check_ir_kind_preserved,
    check_node_multiset_preserved,
    check_stack_paint_order_preserved,
)
from figma_flutter_agent.generator.geometry.invariants.models import GeometryInvariantViolation
from figma_flutter_agent.generator.ir.passes.protocol import Pass
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr

_CLEAN_TREE_PRESERVE_TOKENS = frozenset({"style", "geometry"})


def validate_pass_preserves(
    registered: Pass,
    *,
    before_clean: CleanDesignTreeNode,
    after_clean: CleanDesignTreeNode,
    before_ir: ScreenIr,
    after_ir: ScreenIr,
    omit_ids: frozenset[str] | None = None,
) -> list[GeometryInvariantViolation]:
    """Validate declared ``Pass.preserves`` tokens after a single pass run."""
    violations: list[GeometryInvariantViolation] = []
    preserves = registered.preserves
    if "node_multiset" in preserves:
        violations.extend(
            check_node_multiset_preserved(before_clean, after_clean, omit_ids=omit_ids),
        )
    if "stack_paint_order" in preserves:
        violations.extend(check_stack_paint_order_preserved(before_clean, after_clean))
    if "graph_sync" in preserves:
        violations.extend(check_graph_sync(after_ir, after_clean))
    if preserves & _CLEAN_TREE_PRESERVE_TOKENS:
        violations.extend(check_clean_tree_unchanged(before_clean, after_clean))
    if "kind" in preserves:
        violations.extend(check_ir_kind_preserved(before_ir, after_ir))
    return violations
