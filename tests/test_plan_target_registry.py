"""Tests for diagnose law → plan companion target registry."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.plan_target_registry import (
    companion_targets_for_law,
    enrich_plan_targets,
)


def test_capture_overflow_law_companion_includes_row_policy() -> None:
    law = {
        "id": "capture_runtime_overflow_no_verified_capture",
        "layer": "capture",
    }
    assert companion_targets_for_law(law) == (
        "src/figma_flutter_agent/generator/layout/flex_policy/row.py",
    )


def test_enrich_plan_adds_row_policy_for_capture_overflow_law() -> None:
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": [
                    "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py",
                ],
            }
        ],
    }
    diagnose = {
        "laws": [
            {
                "id": "capture_runtime_overflow_no_verified_capture",
                "layer": "capture",
            }
        ],
    }
    assert enrich_plan_targets(plan, diagnose_payload=diagnose) is True
    targets = plan["steps"][0]["targetFiles"]
    assert "src/figma_flutter_agent/generator/layout/flex_policy/row.py" in targets
