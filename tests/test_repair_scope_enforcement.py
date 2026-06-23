"""Tests for repair scope enforcement and gate path selection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.gates import _split_gate_paths
from figma_flutter_agent.dev.opencode.scope_enforcement import (
    _plan_test_path,
    allowed_paths_for_step,
    capture_worktree_touch_baseline,
    collect_plan_gate_paths,
    collect_plan_target_files,
    collect_repair_gate_paths,
    diff_snapshot,
    diff_touched_paths,
    diff_touched_since_baseline,
    snapshot_tree_hashes,
    validate_scope,
)


def test_collect_plan_target_files_code_change_only() -> None:
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/generator/layout/stack.py"],
                "tests": ["tests/test_layout_flex_policy.py"],
            },
            {
                "actionKind": "REPORT_ONLY",
                "targetFiles": ["should/not/include.py"],
            },
        ],
    }
    paths = collect_plan_target_files(plan)
    assert "src/figma_flutter_agent/generator/layout/stack.py" in paths
    assert "tests/test_layout_flex_policy.py" in paths
    assert "should/not/include.py" not in paths


def test_collect_plan_gate_paths_merges_ruff_and_pytest() -> None:
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/foo.py"],
                "tests": ["tests/test_foo.py"],
            },
        ],
    }
    paths = collect_plan_gate_paths(plan)
    assert "src/figma_flutter_agent/foo.py" in paths
    assert "tests/test_foo.py" in paths


def test_collect_plan_gate_paths_reads_structured_tests() -> None:
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"],
                "tests": [
                    {
                        "name": "test_row_child_width_constraint",
                        "path": "tests/generator/layout/widgets/emit/test_flex.py",
                    }
                ],
            },
        ],
    }
    paths = collect_plan_gate_paths(plan)
    assert "tests/generator/layout/widgets/emit/test_flex.py" in paths


def test_validate_scope_flags_repair_drift() -> None:
    allowed = frozenset({"src/figma_flutter_agent/foo.py"})
    result = validate_scope(
        "repair",
        touched_paths=["src/figma_flutter_agent/bar.py"],
        allowed_paths=allowed,
    )
    assert not result.passed
    assert result.reason_code == "SCOPE_DRIFT"
    assert "bar.py" in result.violations[0]


def test_validate_scope_allows_planned_files_prefix(tmp_path: Path) -> None:
    planned = tmp_path / ".repair" / "candidate" / "planned_files"
    planned.mkdir(parents=True)
    file_path = planned / "screen.dart"
    file_path.write_text("// test", encoding="utf-8")
    allowed = allowed_paths_for_step("fix", worktree=tmp_path, plan_payload={})
    result = validate_scope(
        "fix",
        touched_paths=[".repair/candidate/planned_files/screen.dart"],
        allowed_paths=allowed,
    )
    assert result.passed


def test_split_gate_paths_separates_src_and_tests() -> None:
    ruff_paths, pytest_paths = _split_gate_paths(
        [
            "src/figma_flutter_agent/a.py",
            "tests/test_a.py",
        ],
    )
    assert "src/figma_flutter_agent/a.py" in ruff_paths
    assert "tests/test_a.py" in pytest_paths


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    (path / "README.md").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


@pytest.mark.parametrize("step", ["repair", "fix"])
def test_allowed_paths_for_step_returns_non_empty(tmp_path: Path, step: str) -> None:
    _init_git_repo(tmp_path)
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/x.py"],
                "tests": ["tests/test_x.py"],
            },
        ],
    }
    allowed = allowed_paths_for_step(step, worktree=tmp_path, plan_payload=plan)
    assert allowed


def test_diff_touched_paths_includes_untracked(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    target = tmp_path / "src" / "figma_flutter_agent" / "new_module.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# new\n", encoding="utf-8")
    touched = diff_touched_paths(tmp_path)
    assert "src/figma_flutter_agent/new_module.py" in touched


def test_fix_scope_detects_planned_files_change(tmp_path: Path) -> None:
    planned = tmp_path / ".repair" / "candidate" / "planned_files"
    planned.mkdir(parents=True)
    screen = planned / "screen.dart"
    screen.write_text("// before\n", encoding="utf-8")
    before = snapshot_tree_hashes(planned)
    screen.write_text("// after\n", encoding="utf-8")
    after = snapshot_tree_hashes(planned)
    touched = diff_snapshot(
        before,
        after,
        prefix=".repair/candidate/planned_files",
    )
    allowed = allowed_paths_for_step("fix", worktree=tmp_path, plan_payload={})
    result = validate_scope("fix", touched_paths=touched, allowed_paths=allowed)
    assert result.passed
    assert touched


def test_repair_scope_allows_agent_test_path_when_plan_hallucinates_prefix() -> None:
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": [
                    "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
                ],
                "tests": [
                    "src/figma_flutter_agent/tests/generator/layout/test_flex_emitter.py"
                ],
            },
        ],
    }
    allowed = allowed_paths_for_step("repair", worktree=Path("."), plan_payload=plan)
    touched = [
        "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py",
        "tests/test_flex_emitter.py",
    ]
    result = validate_scope("repair", touched_paths=touched, allowed_paths=allowed)
    assert result.passed
    assert result.reason_code == "SCOPE_OK"


def test_plan_test_path_normalizes_hallucinated_prefix() -> None:
    raw = "src/figma_flutter_agent/tests/generator/layout/test_flex_emitter.py"
    assert _plan_test_path(raw) == "tests/generator/layout/test_flex_emitter.py"


def test_collect_repair_gate_paths_uses_git_touched_test_over_missing_plan_path(
    tmp_path: Path,
) -> None:
    worktree = tmp_path / "wt"
    flex_rel = "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
    flex_path = worktree / flex_rel
    flex_path.parent.mkdir(parents=True)
    flex_path.write_text("# flex\n", encoding="utf-8")
    test_rel = "tests/test_flex_emitter.py"
    test_path = worktree / test_rel
    test_path.parent.mkdir(parents=True)
    test_path.write_text("# test\n", encoding="utf-8")
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": [flex_rel],
                "tests": [
                    "src/figma_flutter_agent/tests/generator/layout/test_flex_emitter.py"
                ],
            },
        ],
    }
    paths = collect_repair_gate_paths(
        plan,
        worktree=worktree,
        git_touched=[flex_rel, test_rel],
    )
    assert flex_rel in paths
    assert test_rel in paths
    assert "tests/generator/layout/test_flex_emitter.py" in paths


def test_touch_baseline_detects_second_edit_to_same_file(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    target = tmp_path / "src" / "figma_flutter_agent" / "module.py"
    target.parent.mkdir(parents=True)
    target.write_text("# v1\n", encoding="utf-8")
    state_dir = tmp_path / ".repair" / "state"
    baseline = capture_worktree_touch_baseline(tmp_path, state_dir)
    assert diff_touched_since_baseline(tmp_path, baseline) == []
    target.write_text("# v2\n", encoding="utf-8")
    touched = diff_touched_since_baseline(tmp_path, baseline)
    assert touched == ["src/figma_flutter_agent/module.py"]


def test_collect_repair_gate_paths_keeps_missing_plan_test_without_fallback(
    tmp_path: Path,
) -> None:
    worktree = tmp_path / "wt"
    flex_rel = "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
    flex_path = worktree / flex_rel
    flex_path.parent.mkdir(parents=True)
    flex_path.write_text("# flex\n", encoding="utf-8")
    missing_test = "tests/test_missing_regression.py"
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": [flex_rel],
                "tests": [missing_test],
            },
        ],
    }
    paths = collect_repair_gate_paths(plan, worktree=worktree)
    assert missing_test in paths
    assert "tests/test_debug_pipeline_models.py" not in paths
