"""Conservation validators for clean-tree and IR dual-graph invariants."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from figma_flutter_agent.generator.geometry.invariants.models import (
    GeometryInvariantViolation,
    geometry_violation,
)
from figma_flutter_agent.generator.ir.passes.sync import index_ir_nodes
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, ScreenIr, WidgetIrNode


@dataclass(frozen=True)
class StyleSnapshot:
    """Tracked style fields for ``inv_style_truth``."""

    font_size: float | None
    text_color: str | None


def conservation_node_multiset(
    tree: CleanDesignTreeNode,
    *,
    omit_ids: frozenset[str] | None = None,
) -> Counter[str]:
    """Count ``node.id`` occurrences over a clean-tree walk.

    Ref-stubs with ``children=[]`` after cluster dedup remain one entry.
    ``flatten_figma_node_ids`` is metadata and is not counted separately.
    """
    omit = omit_ids or frozenset()
    counts: Counter[str] = Counter()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.id not in omit:
            counts[node.id] += 1
        for flat_id in node.flatten_figma_node_ids or ():
            if flat_id not in omit:
                counts[flat_id] += 1
        for child in node.children:
            walk(child)

    walk(tree)
    return counts


def capture_style_baseline(tree: CleanDesignTreeNode) -> dict[str, StyleSnapshot]:
    """Capture fontSize/textColor per node id for style-truth checks."""
    baseline: dict[str, StyleSnapshot] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        baseline[node.id] = StyleSnapshot(
            font_size=node.style.font_size,
            text_color=node.style.text_color,
        )
        for child in node.children:
            walk(child)

    walk(tree)
    return baseline


def _stack_child_orders(root: CleanDesignTreeNode) -> dict[str, list[str]]:
    orders: dict[str, list[str]] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        if node.type == NodeType.STACK:
            orders[node.id] = [child.id for child in node.children]
        for child in node.children:
            walk(child)

    walk(root)
    return orders


def _index_clean_nodes(root: CleanDesignTreeNode) -> dict[str, CleanDesignTreeNode]:
    indexed: dict[str, CleanDesignTreeNode] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        indexed[node.id] = node
        for child in node.children:
            walk(child)

    walk(root)
    return indexed


def collect_subtree_node_ids(
    root: CleanDesignTreeNode,
    subtree_root_ids: frozenset[str],
) -> frozenset[str]:
    """Collect all node ids under ``subtree_root_ids`` in ``root``."""
    indexed = _index_clean_nodes(root)
    collected: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        collected.add(node.id)
        for child in node.children:
            walk(child)

    for node_id in subtree_root_ids:
        node = indexed.get(node_id)
        if node is not None:
            walk(node)
    return frozenset(collected)


def check_node_multiset_preserved(
    baseline: CleanDesignTreeNode,
    current: CleanDesignTreeNode,
    *,
    omit_ids: frozenset[str] | None = None,
    allowed_removed_ids: frozenset[str] | None = None,
) -> list[GeometryInvariantViolation]:
    """Return violations when node-id multiset changes between snapshots."""
    expected = conservation_node_multiset(baseline, omit_ids=omit_ids)
    actual = conservation_node_multiset(current, omit_ids=omit_ids)
    if allowed_removed_ids:
        for node_id in allowed_removed_ids:
            if node_id in expected:
                del expected[node_id]
    if expected == actual:
        return []
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    detail_parts: list[str] = []
    if missing:
        detail_parts.append(f"missing={missing[:6]}")
    if extra:
        detail_parts.append(f"extra={extra[:6]}")
    return [
        geometry_violation(
            code="inv_node_multiset",
            node_id=missing[0] if missing else (extra[0] if extra else baseline.id),
            detail="; ".join(detail_parts) or "multiset mismatch",
        ),
    ]


def check_stack_paint_order_preserved(
    baseline: CleanDesignTreeNode,
    current: CleanDesignTreeNode,
) -> list[GeometryInvariantViolation]:
    """Return violations when STACK child paint order diverges from baseline."""
    baseline_orders = _stack_child_orders(baseline)
    current_orders = _stack_child_orders(current)
    violations: list[GeometryInvariantViolation] = []
    for stack_id, expected_order in baseline_orders.items():
        if stack_id not in current_orders:
            continue
        actual_order = current_orders.get(stack_id)
        if actual_order != expected_order:
            violations.append(
                geometry_violation(
                    code="inv_stack_paint_order",
                    node_id=stack_id,
                    detail=f"expected {expected_order}, got {actual_order}",
                ),
            )
    return violations


def check_graph_sync(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
) -> list[GeometryInvariantViolation]:
    """Return violations when IR and clean-tree child structure disagree."""
    ir_index = index_ir_nodes(screen_ir.root)
    clean_index = _index_clean_nodes(clean_tree)
    violations: list[GeometryInvariantViolation] = []
    for figma_id, ir_node in ir_index.items():
        clean_node = clean_index.get(figma_id)
        if clean_node is None:
            violations.append(
                geometry_violation(
                    code="inv_graph_sync",
                    node_id=figma_id,
                    detail="IR node missing from clean tree",
                ),
            )
            continue
        ir_child_ids = {child.figma_id for child in ir_node.children}
        clean_child_ids = {child.id for child in clean_node.children}
        if ir_child_ids != clean_child_ids:
            violations.append(
                geometry_violation(
                    code="inv_graph_sync",
                    node_id=figma_id,
                    detail=(
                        f"child id set mismatch IR={sorted(ir_child_ids)} "
                        f"clean={sorted(clean_child_ids)}"
                    ),
                ),
            )
    return violations


def check_style_truth(
    baseline: dict[str, StyleSnapshot],
    current: CleanDesignTreeNode,
    *,
    allowed_mutations: dict[tuple[str, str], str] | None = None,
) -> list[GeometryInvariantViolation]:
    """Return violations when style fields drift without a named policy."""
    allowed = allowed_mutations or {}
    violations: list[GeometryInvariantViolation] = []

    def walk(node: CleanDesignTreeNode) -> None:
        snap = baseline.get(node.id)
        if snap is not None:
            if snap.font_size != node.style.font_size:
                policy = allowed.get((node.id, "font_size"))
                if policy is None:
                    violations.append(
                        geometry_violation(
                            code="inv_style_truth",
                            node_id=node.id,
                            detail=f"font_size {snap.font_size} -> {node.style.font_size}",
                        ),
                    )
            if snap.text_color != node.style.text_color:
                policy = allowed.get((node.id, "text_color"))
                if policy is None:
                    violations.append(
                        geometry_violation(
                            code="inv_style_truth",
                            node_id=node.id,
                            detail=f"text_color {snap.text_color} -> {node.style.text_color}",
                        ),
                    )
        for child in node.children:
            walk(child)

    walk(current)
    return violations


def allowed_style_mutations_from_provenance(
    mutations: list[Any],
) -> dict[tuple[str, str], str]:
    """Build policy map from provenance mutations for ``inv_style_truth``."""
    allowed: dict[tuple[str, str], str] = {}
    for item in mutations:
        policy = getattr(item, "policy", None)
        if policy is None:
            continue
        field = getattr(item, "field", None)
        node_id = getattr(item, "node_id", None)
        if field and node_id:
            allowed[(node_id, field)] = policy
    return allowed


def check_type_truth(
    baseline: dict[str, NodeType],
    current: CleanDesignTreeNode,
    *,
    allowed_mutations: dict[tuple[str, str], str] | None = None,
) -> list[GeometryInvariantViolation]:
    """Return violations when ``node.type`` drifts without a named policy."""
    allowed = allowed_mutations or {}
    violations: list[GeometryInvariantViolation] = []

    def walk(node: CleanDesignTreeNode) -> None:
        expected = baseline.get(node.id)
        if expected is not None and expected != node.type:
            policy = allowed.get((node.id, "type"))
            if policy is None:
                violations.append(
                    geometry_violation(
                        code="inv_type_truth",
                        node_id=node.id,
                        detail=f"type {expected.value} -> {node.type.value}",
                    ),
                )
        for child in node.children:
            walk(child)

    walk(current)
    return violations


_IR_CLASSIFICATION_EXCLUDE = frozenset(
    {
        "kind",
        "payload",
        "classification_hint",
        "is_selected",
        "hint_text",
        "error_text",
        "is_multiline",
        "max_lines",
        "children",
    }
)


def _ir_non_classification_dump(node: WidgetIrNode) -> dict[str, object]:
    return node.model_dump(by_alias=True, exclude=_IR_CLASSIFICATION_EXCLUDE)


def check_ir_classification_scope(
    baseline: ScreenIr,
    current: ScreenIr,
) -> list[GeometryInvariantViolation]:
    """Ensure classification only mutates semantic annotation fields on IR."""
    violations: list[GeometryInvariantViolation] = []

    def walk(base: WidgetIrNode, cur: WidgetIrNode) -> None:
        if base.figma_id != cur.figma_id:
            violations.append(
                geometry_violation(
                    code="inv_classification_scope",
                    node_id=cur.figma_id,
                    detail="figma id mismatch during classification",
                ),
            )
            return
        base_child_ids = [child.figma_id for child in base.children]
        cur_child_ids = [child.figma_id for child in cur.children]
        if base_child_ids != cur_child_ids:
            violations.append(
                geometry_violation(
                    code="inv_classification_scope",
                    node_id=cur.figma_id,
                    detail=f"child order changed {base_child_ids} -> {cur_child_ids}",
                ),
            )
        if _ir_non_classification_dump(base) != _ir_non_classification_dump(cur):
            violations.append(
                geometry_violation(
                    code="inv_classification_scope",
                    node_id=cur.figma_id,
                    detail="non-classification IR fields mutated",
                ),
            )
        for base_child, cur_child in zip(base.children, cur.children, strict=False):
            walk(base_child, cur_child)

    walk(baseline.root, current.root)
    if baseline.stack_child_order != current.stack_child_order:
        violations.append(
            geometry_violation(
                code="inv_classification_scope",
                node_id=baseline.root.figma_id,
                detail="stackChildOrder mutated during classification",
            ),
        )
    return violations


def check_clean_tree_unchanged(
    baseline: CleanDesignTreeNode,
    current: CleanDesignTreeNode,
) -> list[GeometryInvariantViolation]:
    """Return violations when clean-tree structure or geometry drifts."""
    violations: list[GeometryInvariantViolation] = []

    def walk(base: CleanDesignTreeNode, cur: CleanDesignTreeNode) -> None:
        if base.id != cur.id:
            return
        if base.model_dump(by_alias=True) != cur.model_dump(by_alias=True):
            if base.type != cur.type:
                violations.append(
                    geometry_violation(
                        code="inv_classification_scope",
                        node_id=cur.id,
                        detail="clean-tree node mutated during classification",
                    ),
                )
            elif [child.id for child in base.children] != [child.id for child in cur.children]:
                violations.append(
                    geometry_violation(
                        code="inv_classification_scope",
                        node_id=cur.id,
                        detail="clean-tree children changed during classification",
                    ),
                )
            else:
                violations.append(
                    geometry_violation(
                        code="inv_classification_scope",
                        node_id=cur.id,
                        detail="clean-tree fields mutated during classification",
                    ),
                )
        for base_child, cur_child in zip(base.children, cur.children, strict=False):
            walk(base_child, cur_child)

    walk(baseline, current)
    return violations
