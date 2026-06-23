"""Tests for compact OpenCode repair write prompts."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.dev.opencode.chain_compact import compact_plan_for_repair
from figma_flutter_agent.dev.opencode.l6_context import build_l6_bindings
from figma_flutter_agent.dev.opencode.l6_run_context import run_context_for_l6_json
from figma_flutter_agent.dev.opencode.prompt_context import build_write_step_user_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.repair_prompt import _MAX_REPAIR_WRITE_PROMPT_CHARS


def test_run_context_for_l6_omits_nested_bindings() -> None:
    nested = {"run_context_json": "x" * 50_000}
    sanitized = run_context_for_l6_json(
        {"case_mode": "FORENSIC", "_l6_bindings": nested},
    )
    assert sanitized == {"case_mode": "FORENSIC"}
    assert "_l6_bindings" not in sanitized


def test_compact_run_context_drops_vision_bundle() -> None:
    from figma_flutter_agent.dev.opencode.repair_prompt import compact_run_context_for_write

    compact = compact_run_context_for_write(
        {
            "case_mode": "FORENSIC",
            "planStepOrders": [1],
            "vision_bundle": {"huge": "x" * 50_000},
            "review_rubric": {"noise": True},
        },
    )
    assert compact["case_mode"] == "FORENSIC"
    assert "vision_bundle" not in compact
    assert "review_rubric" not in compact


def test_plan_scoped_repo_map_only_target_files() -> None:
    plan = {
        "steps": [
            {
                "order": 1,
                "actionKind": "CODE_CHANGE",
                "lawId": "a",
                "targetFiles": ["src/x.py"],
            },
            {"order": 2, "actionKind": "REPORT_ONLY", "lawId": "b"},
        ],
    }
    compact = compact_plan_for_repair(plan, plan_step_orders=[1])
    assert len(compact["steps"]) == 1
    assert compact["steps"][0]["lawId"] == "a"


def test_compact_plan_for_repair_accepts_string_order() -> None:
    plan = {
        "steps": [
            {
                "order": "1",
                "actionKind": "CODE_CHANGE",
                "lawId": "law-a",
                "targetFiles": ["src/x.py"],
                "tests": ["tests/test_x.py"],
            }
        ]
    }
    compact = compact_plan_for_repair(plan, plan_step_orders=[1])
    assert len(compact["steps"]) == 1
    assert compact["steps"][0]["order"] == 1


def test_repair_write_prompt_does_not_ask_for_repair_json(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    debug_mirror = worktree / ".repair" / "debug" / "limbo" / "login"
    debug_mirror.mkdir(parents=True)
    chain = ReasoningChain()
    chain.append(
        "recognise", {"symptoms": [{"id": "s1", "description": "overflow " * 200}]}
    )
    chain.append(
        "inspect",
        {
            "entities": [
                {
                    "id": "e1",
                    "summary": "x" * 5000,
                    "repoPaths": [
                        "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
                    ],
                }
            ],
        },
    )
    chain.append(
        "diagnose",
        {
            "laws": [
                {
                    "id": "law-flex",
                    "repairShape": "emitter " * 300,
                    "evidence": [{"excerpt": "y" * 3000}],
                }
            ],
        },
    )
    plan = {
        "steps": [
            {
                "order": 1,
                "actionKind": "CODE_CHANGE",
                "lawId": "law-flex",
                "targetFiles": [
                    "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
                ],
                "tests": [{"path": "tests/test_flex.py"}],
                "expectedChange": "z" * 2000,
            }
        ],
    }
    chain.append("plan", plan)
    state_dir = worktree / ".repair" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace

    workspace = RepairWorkspace(
        case_id="c",
        worktree=worktree,
        repair_root=worktree / ".repair",
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=worktree / ".repair" / "manifest.json",
    )
    bindings = build_l6_bindings(
        step="repair",
        board="forensic",
        workspace=workspace,
        feature="login",
        project_label="limbo",
        run_context={
            "case_mode": "FORENSIC",
            "planStepOrders": [1],
            "vision_bundle": {"blob": "w" * 100_000},
        },
        reasoning_chain_json="{}",
        chain=chain,
        plan=plan,
    )
    prompt = build_write_step_user_prompt(
        "repair",
        feature="login",
        board="forensic",
        worktree=worktree,
        debug_mirror=debug_mirror,
        chain=chain,
        run_context={
            "case_mode": "FORENSIC",
            "planStepOrders": [1],
            "vision_bundle": {"blob": "w" * 100_000},
        },
        l6_bindings=bindings,
        plan=plan,
    )
    assert len(prompt) <= _MAX_REPAIR_WRITE_PROMPT_CHARS
    assert "<L1:PURPOSE>" in prompt
    assert "repair-invariants" in prompt.lower() or "Fix the law" in prompt
    assert "flex.py" in prompt
    assert "plan.json" in prompt or "plan_state_path" in prompt
    assert "write repair.json when done" not in prompt.lower()
    assert "orchestrator records repair state" in prompt.lower()
