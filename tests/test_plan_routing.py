"""Tests for repair plan step routing."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.plan_routing import (
    assign_repair_plan_step_orders,
    collect_repair_plan_step_orders,
)


def test_collect_repair_plan_step_orders_code_change_only() -> None:
    plan = {
        "steps": [
            {"order": 1, "actionKind": "CODE_CHANGE", "lawId": "law_a"},
            {"order": 2, "actionKind": "REPORT_ONLY", "lawId": "law_b"},
            {"order": 3, "actionKind": "CODE_CHANGE", "lawId": "law_c"},
        ],
    }
    assert collect_repair_plan_step_orders(plan) == [1, 3]


def test_assign_repair_plan_step_orders_writes_run_context() -> None:
    run_context: dict[str, object] = {}
    plan = {"steps": [{"order": 2, "actionKind": "CODE_CHANGE", "lawId": "law_x"}]}
    orders = assign_repair_plan_step_orders(run_context, plan)
    assert orders == [2]
    assert run_context["planStepOrders"] == [2]
