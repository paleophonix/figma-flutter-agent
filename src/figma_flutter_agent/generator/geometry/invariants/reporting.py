"""Reporting helpers for geometry invariant violations."""

from __future__ import annotations

from collections import Counter

from figma_flutter_agent.generator.geometry.invariants.models import (
    GeometryInvariantViolation,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode


def partition_geometry_violations(
    violations: list[GeometryInvariantViolation],
) -> tuple[list[GeometryInvariantViolation], list[GeometryInvariantViolation]]:
    """Split violations into hard (fail-closed) and soft (log+degrade) lists."""
    hard = [item for item in violations if item.severity == "hard"]
    soft = [item for item in violations if item.severity == "soft"]
    return hard, soft


def count_violations_by_code(
    violations: list[GeometryInvariantViolation],
) -> dict[str, int]:
    """Count violations grouped by code (for telemetry)."""
    return dict(Counter(item.code for item in violations))


def raise_on_hard_geometry_violations(
    violations: list[GeometryInvariantViolation],
    *,
    context: str,
) -> list[GeometryInvariantViolation]:
    """Log soft violations; raise ``GenerationError`` only when hard violations exist."""
    hard, soft = partition_geometry_violations(violations)
    if soft:
        summary = "; ".join(f"{v.code}@{v.node_id}" for v in soft[:6])
        extra = len(soft) - 6
        suffix = f" (+{extra} more)" if extra > 0 else ""
        from figma_flutter_agent.pipeline.warning_policy import log_recoverable_debug

        log_recoverable_debug(
            "Geometry soft invariant violations ({}){}: {}",
            context,
            suffix,
            summary,
        )
    if not hard:
        return soft
    summary = "; ".join(f"{v.code}@{v.node_id}" for v in hard[:6])
    extra = len(hard) - 6
    suffix = f" (+{extra} more)" if extra > 0 else ""
    from figma_flutter_agent.errors import GenerationError

    raise GenerationError(f"Geometry invariant violations ({context}): {summary}{suffix}")


def mark_degraded_nodes(
    root: CleanDesignTreeNode,
    soft_violations: list[GeometryInvariantViolation],
) -> CleanDesignTreeNode:
    """Mark ``layout_slot.degraded`` on nodes with soft invariant violations."""
    if not soft_violations:
        return root
    degraded_ids = {item.node_id for item in soft_violations}

    def visit(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        new_children: list[CleanDesignTreeNode] = []
        children_changed = False
        for child in node.children:
            updated_child = visit(child)
            new_children.append(updated_child)
            if updated_child is not child:
                children_changed = True
        slot = node.layout_slot
        if node.id in degraded_ids and slot is not None and not slot.degraded:
            slot = slot.model_copy(update={"degraded": True})
            return node.model_copy(update={"layout_slot": slot, "children": new_children})
        if children_changed:
            return node.model_copy(update={"children": new_children})
        return node

    return visit(root)
