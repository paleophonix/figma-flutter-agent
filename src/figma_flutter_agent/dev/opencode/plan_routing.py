"""Plan step routing for OpenCode repair and fix write steps."""

from __future__ import annotations

from typing import Any

_CODE_CHANGE_KIND = "CODE_CHANGE"


def coerce_plan_step_order(item: dict[str, Any]) -> int | None:
    """Normalize a plan step ``order`` field to an integer when possible."""
    raw = item.get("order")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    return None


_step_order = coerce_plan_step_order


def collect_repair_plan_step_orders(plan_payload: dict[str, Any]) -> list[int]:
    """Return sorted CODE_CHANGE plan step orders assigned to the repair pass.

    Args:
        plan_payload: Parsed executive plan JSON.

    Returns:
        Distinct ascending ``order`` values for CODE_CHANGE steps only.
    """
    orders: list[int] = []
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return []
    for item in steps:
        if not isinstance(item, dict):
            continue
        action_kind = str(item.get("actionKind") or _CODE_CHANGE_KIND).upper()
        if action_kind != _CODE_CHANGE_KIND:
            continue
        order = _step_order(item)
        if order is not None:
            orders.append(order)
    return sorted(set(orders))


def assign_repair_plan_step_orders(
    run_context: dict[str, Any],
    plan_payload: dict[str, Any],
) -> list[int]:
    """Write orchestrator-assigned ``planStepOrders`` into ``run_context``.

    Args:
        run_context: Mutable pipeline run context for prompt assembly.
        plan_payload: Parsed executive plan JSON.

    Returns:
        Assigned CODE_CHANGE step orders for this repair pass.
    """
    orders = collect_repair_plan_step_orders(plan_payload)
    run_context["planStepOrders"] = orders
    return orders
