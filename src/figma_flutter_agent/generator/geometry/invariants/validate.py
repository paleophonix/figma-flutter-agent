"""Geometry invariant validation orchestration."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.checks import (
    NODE_CHECKS,
    _check_inv_flex_axis,
)
from figma_flutter_agent.generator.geometry.invariants.models import (
    GeometryInvariantViolation,
    geometry_violation,
)
from figma_flutter_agent.generator.geometry.invariants.reporting import (
    partition_geometry_violations,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode


def validate_geometry_invariants(
    root: CleanDesignTreeNode,
    *,
    require_layout_slots: bool = False,
    layout_source: str | None = None,
    sidecar_skipped: bool = False,
    strict_invariants: bool = False,
) -> list[GeometryInvariantViolation]:
    """Validate translation-theory geometry invariants on a clean tree."""
    violations: list[GeometryInvariantViolation] = []
    has_layout_slots = False

    def visit(parent: CleanDesignTreeNode | None, node: CleanDesignTreeNode) -> None:
        nonlocal has_layout_slots
        if node.layout_slot is not None:
            has_layout_slots = True
        if require_layout_slots and node.layout_slot is None:
            violations.append(
                geometry_violation(
                    code="missing_layout_slot",
                    node_id=node.id,
                    detail="geometry planner did not attach layout_slot",
                )
            )
            return
        for check in NODE_CHECKS:
            item = check(node)
            if item is not None:
                violations.append(item)
        flex_axis = _check_inv_flex_axis(node, parent)
        if flex_axis is not None:
            violations.append(flex_axis)
        for child in node.children:
            visit(node, child)

    visit(None, root)
    if layout_source or has_layout_slots:
        from figma_flutter_agent.generator.geometry.emit_invariants import (
            validate_ast_coverage,
            validate_emit_geometry_invariants,
        )

        if layout_source:
            violations.extend(validate_emit_geometry_invariants(root, layout_source))
        violations.extend(
            validate_ast_coverage(
                root,
                layout_source or "",
                sidecar_skipped=sidecar_skipped,
                strict=strict_invariants,
            )
        )
    return violations


def assert_geometry_invariants_clean(
    root: CleanDesignTreeNode,
    *,
    require_layout_slots: bool = False,
    layout_source: str | None = None,
    strict_invariants: bool = False,
    hard_only: bool = True,
) -> None:
    """Raise when geometry invariant violations exist (hard-only by default)."""
    violations = validate_geometry_invariants(
        root,
        require_layout_slots=require_layout_slots,
        layout_source=layout_source,
        strict_invariants=strict_invariants,
    )
    if hard_only:
        hard, _ = partition_geometry_violations(violations)
        violations = hard
    if not violations:
        return
    summary = "; ".join(f"{v.code}@{v.node_id}" for v in violations[:8])
    extra = len(violations) - 8
    suffix = f" (+{extra} more)" if extra > 0 else ""
    from figma_flutter_agent.errors import GenerationError

    raise GenerationError(f"Geometry invariant violations: {summary}{suffix}")
