"""Tests for repair scope enforcement and gate path selection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.gates import _split_gate_paths
from figma_flutter_agent.dev.opencode.scope_enforcement import (
    allowed_paths_for_step,
    collect_plan_gate_paths,
    collect_plan_target_files,
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
