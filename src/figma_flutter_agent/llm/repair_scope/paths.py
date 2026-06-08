"""Repair scope path helpers."""

from __future__ import annotations

from figma_flutter_agent.llm.repair_scope.models import RepairScope


def expand_ast_reconcile_paths(
    paths: frozenset[str],
    planned: dict[str, str],
    *,
    resolved_feature: str,
) -> frozenset[str]:
    """Expand a set of repair paths to include the paired layout file."""
    layout_key = f"lib/generated/{resolved_feature}_layout.dart"
    extra: set[str] = set()
    if layout_key in planned:
        extra.add(layout_key)
    return paths | frozenset(extra)


def repair_scope_planned_paths(scope: RepairScope) -> frozenset[str]:
    """Return normalized planned paths touched by a repair scope."""
    return frozenset(
        target.planned_path.replace("\\", "/")
        for target in scope.targets
        if target.planned_path
    )
