"""Tests for per-step L6 allowlists and file-first repair bindings."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.dev.opencode.l6_allowlist import l6_binding_keys_for
from figma_flutter_agent.dev.opencode.l6_context import build_l6_bindings
from figma_flutter_agent.dev.opencode.prompt_context import build_write_step_user_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace


def _workspace(tmp_path: Path) -> RepairWorkspace:
    worktree = tmp_path / "wt"
    repair_root = worktree / ".repair"
    state_dir = repair_root / "state"
    debug_mirror = repair_root / "debug" / "limbo" / "login"
    state_dir.mkdir(parents=True)
    debug_mirror.mkdir(parents=True)
    manifest_path = repair_root / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    return RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=repair_root,
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=manifest_path,
    )


def test_repair_allowlist_is_file_first() -> None:
    keys = l6_binding_keys_for("repair", board="forensic")
    assert "plan_state_path" in keys
    assert "diagnose_state_path" in keys
    assert "reasoning_chain_json" not in keys
    assert "repo_map_deep_json" not in keys
    assert "vision_bundle_json" not in keys


def test_plan_allowlist_includes_catalog_not_vision() -> None:
    keys = l6_binding_keys_for("plan", board="forensic")
    assert "compiler_path_catalog_json" in keys
    assert "repo_map_deep_json" in keys
    assert "vision_bundle_json" not in keys


def test_build_l6_bindings_repair_omits_chain_and_repo_map(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    chain = ReasoningChain(
        steps={
            "diagnose": {
                "laws": [
                    {
                        "id": "law-flex",
                        "repairShape": {"target": "emitter"},
                    }
                ]
            }
        }
    )
    plan = {
        "steps": [
            {
                "order": 1,
                "actionKind": "CODE_CHANGE",
                "lawId": "law-flex",
                "targetFiles": ["src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"],
                "tests": [{"path": "tests/test_flex.py"}],
            }
        ]
    }
    bindings = build_l6_bindings(
        step="repair",
        board="forensic",
        workspace=workspace,
        feature="login",
        project_label="limbo",
        run_context={
            "case_mode": "FORENSIC",
            "planStepOrders": [1],
            "vision_bundle": {"blob": "x" * 100_000},
        },
        reasoning_chain_json='{"noise": true}',
        chain=chain,
        plan=plan,
    )
    assert "reasoning_chain_json" not in bindings
    assert "repo_map_deep_json" not in bindings
    assert "plan_state_path" in bindings
    assert "law-flex" in bindings["diagnose_laws_json"]
    assert "flex.py" in bindings["allowed_edit_scope_json"]
    assert "vision_bundle" not in bindings["run_context_json"]


def test_repair_write_prompt_file_first_and_bounded(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    chain = ReasoningChain()
    chain.append(
        "diagnose",
        {
            "laws": [
                {
                    "id": "law-flex",
                    "evidence": [{"excerpt": "z" * 8000}],
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
                "targetFiles": ["src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"],
                "tests": [{"path": "tests/test_flex.py"}],
            }
        ]
    }
    chain.append("plan", plan)
    bindings = build_l6_bindings(
        step="repair",
        board="forensic",
        workspace=workspace,
        feature="login",
        project_label="limbo",
        run_context={"case_mode": "FORENSIC", "planStepOrders": [1]},
        reasoning_chain_json="{}",
        chain=chain,
        plan=plan,
    )
    prompt = build_write_step_user_prompt(
        "repair",
        feature="login",
        board="forensic",
        worktree=workspace.worktree,
        debug_mirror=workspace.debug_mirror,
        chain=chain,
        run_context={"case_mode": "FORENSIC", "planStepOrders": [1]},
        l6_bindings=bindings,
        plan=plan,
    )
    assert len(prompt) < 20_000
    assert "plan.json" in prompt
    assert "diagnose.json" in prompt
    assert "<L1:PURPOSE>" in prompt
    assert "stack.py" not in prompt or "selectedPaths" not in prompt
