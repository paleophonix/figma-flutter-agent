"""Per-pass preservation contract validation for IR layout passes."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_clean_tree_unchanged,
    check_graph_sync,
    check_ir_kind_preserved,
    check_node_multiset_preserved,
    check_stack_paint_order_preserved,
)
from figma_flutter_agent.generator.geometry.invariants.models import (
    GeometryInvariantViolation,
    geometry_violation,
)
from figma_flutter_agent.generator.ir.passes.protocol import Pass
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr

_CLEAN_TREE_PRESERVE_TOKENS = frozenset({"style", "geometry"})

_CLEAN_FIELD_TOKENS: tuple[tuple[str, str], ...] = (
    ("type", "type"),
    ("sizing", "sizing"),
    ("style", "style"),
    ("stack_placement", "stack_placement"),
    ("scroll_axis", "scroll_axis"),
    ("spacing", "spacing"),
    ("flex_gap_mode", "flex_gap_mode"),
    ("flex_explicit_gaps", "flex_explicit_gaps"),
    ("layout_positioning", "layout_positioning"),
    ("layout_role", "layout_role"),
    ("layout_hints", "layout_hints"),
    ("layout_slot", "layout_slot"),
    ("kind", "kind"),
)


def _changed_clean_tree_tokens(
    before: CleanDesignTreeNode,
    after: CleanDesignTreeNode,
) -> set[str]:
    """Return declared mutate tokens that differ between two node snapshots."""
    changed: set[str] = set()
    before_dump = before.model_dump(by_alias=True)
    after_dump = after.model_dump(by_alias=True)
    for field, token in _CLEAN_FIELD_TOKENS:
        if before_dump.get(field) != after_dump.get(field):
            changed.add(token)
    if [child.id for child in before.children] != [
        child.id for child in after.children
    ]:
        changed.add("children")
    return changed


def _walk_clean_pairs(
    before: CleanDesignTreeNode,
    after: CleanDesignTreeNode,
) -> list[tuple[CleanDesignTreeNode, CleanDesignTreeNode]]:
    pairs: list[tuple[CleanDesignTreeNode, CleanDesignTreeNode]] = [(before, after)]

    def walk(base: CleanDesignTreeNode, cur: CleanDesignTreeNode) -> None:
        after_by_id = {child.id: child for child in cur.children}
        for base_child in base.children:
            cur_child = after_by_id.get(base_child.id)
            if cur_child is not None:
                pairs.append((base_child, cur_child))
                walk(base_child, cur_child)

    walk(before, after)
    return pairs


def validate_pass_mutates(
    registered: Pass,
    *,
    before_clean: CleanDesignTreeNode,
    after_clean: CleanDesignTreeNode,
    before_ir: ScreenIr,
    after_ir: ScreenIr,
) -> list[GeometryInvariantViolation]:
    """Validate that a pass only mutates fields declared in ``Pass.mutates``."""
    _ = before_ir, after_ir
    allowed = registered.mutates
    violations: list[GeometryInvariantViolation] = []
    for before_node, after_node in _walk_clean_pairs(before_clean, after_clean):
        changed = _changed_clean_tree_tokens(before_node, after_node)
        disallowed = changed - allowed
        for token in sorted(disallowed):
            violations.append(
                geometry_violation(
                    code="pass_over_mutation",
                    node_id=after_node.id,
                    detail=f"{registered.name} mutated {token} without declaring mutates",
                ),
            )
    return violations


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
