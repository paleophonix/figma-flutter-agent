"""Tests for repair worktree salvage after noop or blocked plan."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.check import compiler_repair_verified
from figma_flutter_agent.dev.opencode.gates import GateResult
from figma_flutter_agent.dev.opencode.repair_salvage import (
    attempt_worktree_compiler_salvage,
    collect_pending_compiler_gate_paths,
    plan_allows_worktree_salvage,
)
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    (path / "README.md").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def _workspace(tmp_path: Path) -> RepairWorkspace:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    repair_root = worktree / ".repair"
    state_dir = repair_root / "state"
    state_dir.mkdir(parents=True)
    debug_mirror = repair_root / "debug" / "limbo" / "login_version_1"
    debug_mirror.mkdir(parents=True)
    manifest = repair_root / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    return RepairWorkspace(
        case_id="test-case",
        worktree=worktree,
        repair_root=repair_root,
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=manifest,
    )


def test_plan_allows_worktree_salvage_when_blocked_or_empty() -> None:
    assert plan_allows_worktree_salvage({"blocked": True, "steps": []})
    assert plan_allows_worktree_salvage({"steps": []})
    assert not plan_allows_worktree_salvage(
        {
            "steps": [
                {
                    "actionKind": "CODE_CHANGE",
                    "targetFiles": ["src/figma_flutter_agent/generator/x.py"],
                }
            ]
        }
    )


def test_collect_pending_compiler_gate_paths_skips_repair_debug(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    compiler = tmp_path / "src" / "figma_flutter_agent" / "generator" / "row.py"
    compiler.parent.mkdir(parents=True)
    compiler.write_text("# edit\n", encoding="utf-8")
    (tmp_path / ".repair" / "state").mkdir(parents=True)
    (tmp_path / ".repair" / "state" / "plan.json").write_text("{}", encoding="utf-8")
    pending = collect_pending_compiler_gate_paths(tmp_path)
    assert pending == ["src/figma_flutter_agent/generator/row.py"]


def test_attempt_worktree_compiler_salvage_returns_payload_when_gates_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _init_git_repo(workspace.worktree)
    target = (
        workspace.worktree
        / "src"
        / "figma_flutter_agent"
        / "generator"
        / "layout"
        / "flex_policy"
        / "row.py"
    )
    target.parent.mkdir(parents=True)
    target.write_text("# patched\n", encoding="utf-8")
    test_file = workspace.worktree / "tests" / "test_emitter_flex_row_constraint.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_row() -> None:\n    assert True\n", encoding="utf-8")

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.repair_salvage.run_repair_gates",
        lambda worktree, touched_paths=None: GateResult(
            passed=True,
            ruff_ok=True,
            pytest_ok=True,
            ruff_output="",
            pytest_output="",
            touched_paths=tuple(touched_paths or ()),
            skipped=False,
        ),
    )

    salvage = attempt_worktree_compiler_salvage(
        workspace,
        plan_payload={"blocked": True, "steps": []},
    )
    assert salvage is not None
    assert salvage["salvaged"] is True
    assert salvage["noop"] is False
    assert "src/figma_flutter_agent/generator/layout/flex_policy/row.py" in salvage["filesTouched"]
    assert compiler_repair_verified(salvage, {"blocked": True, "steps": []})


def test_attempt_worktree_compiler_salvage_none_without_compiler_edits(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _init_git_repo(workspace.worktree)
    salvage = attempt_worktree_compiler_salvage(
        workspace,
        plan_payload={"blocked": True, "steps": []},
    )
    assert salvage is None


def test_salvage_requires_diagnose_law_ownership_when_plan_not_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _init_git_repo(workspace.worktree)
    target = (
        workspace.worktree
        / "src"
        / "figma_flutter_agent"
        / "generator"
        / "layout"
        / "flex_policy"
        / "row.py"
    )
    target.parent.mkdir(parents=True)
    target.write_text("# patched\n", encoding="utf-8")

    salvage = attempt_worktree_compiler_salvage(
        workspace,
        plan_payload={"steps": []},
        diagnose_payload={"laws": [{"lawId": "CaptureLaw", "layer": "capture"}]},
    )
    assert salvage is None

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.repair_salvage.run_repair_gates",
        lambda worktree, touched_paths=None: GateResult(
            passed=True,
            ruff_ok=True,
            pytest_ok=True,
            ruff_output="",
            pytest_output="",
            touched_paths=tuple(touched_paths or ()),
            skipped=False,
        ),
    )
    salvage = attempt_worktree_compiler_salvage(
        workspace,
        plan_payload={"steps": []},
        diagnose_payload={"laws": [{"lawId": "FlexRowOverflowLaw", "layer": "emit"}]},
    )
    assert salvage is not None
