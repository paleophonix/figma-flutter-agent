"""Tests for post-repair quality gates."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.dev.opencode.gates import (
    _run_poetry_cmd,
    _worktree_absolute_gate_paths,
    ensure_worktree_poetry_env,
    skipped_repair_gate_result,
)


def test_skipped_repair_gate_result_passes() -> None:
    result = skipped_repair_gate_result(touched_paths=("tests/test_foo.py",))
    assert result.passed
    assert result.skipped
    assert result.ruff_ok
    assert result.pytest_ok


def test_ensure_worktree_poetry_env_installs_when_probe_fails(tmp_path: Path) -> None:
    worktree = tmp_path / "repo"
    worktree.mkdir()
    (worktree / "pyproject.toml").write_text("[tool.poetry]\nname='x'\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def _fake_poetry(worktree_arg: Path, *args: str, timeout: int = 600) -> tuple[int, str]:
        calls.append(args)
        if args[:2] == ("run", "python"):
            return 1, "ModuleNotFoundError"
        return 0, ""

    with patch("figma_flutter_agent.dev.opencode.gates._run_poetry_cmd", side_effect=_fake_poetry):
        ensure_worktree_poetry_env(worktree)

    assert ("install", "--with", "dev", "--no-interaction") in calls


def test_ensure_worktree_poetry_env_skips_when_probe_passes(tmp_path: Path) -> None:
    worktree = tmp_path / "repo"
    worktree.mkdir()
    (worktree / "pyproject.toml").write_text("[tool.poetry]\nname='x'\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def _fake_poetry(worktree_arg: Path, *args: str, timeout: int = 600) -> tuple[int, str]:
        calls.append(args)
        return 0, ""

    with patch("figma_flutter_agent.dev.opencode.gates._run_poetry_cmd", side_effect=_fake_poetry):
        ensure_worktree_poetry_env(worktree)

    assert calls == [("run", "python", "-c", "import prometheus_client")]


def test_run_poetry_cmd_uses_project_directory_flag(tmp_path: Path, monkeypatch) -> None:
    worktree = tmp_path / "repo"
    worktree.mkdir()
    captured: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        captured.append(cmd)

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    _run_poetry_cmd(worktree, "run", "pytest", "-q", "tests/test_foo.py")
    assert captured[0][:3] == ["poetry", "-P", str(worktree.resolve())]
    assert captured[0][3:] == ["run", "pytest", "-q", "tests/test_foo.py"]


def test_worktree_absolute_gate_paths_resolve_under_worktree(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    test_rel = "tests/test_flex_emitter.py"
    test_path = worktree / test_rel
    test_path.parent.mkdir(parents=True)
    test_path.write_text("# test\n", encoding="utf-8")
    resolved = _worktree_absolute_gate_paths(worktree, [test_rel])
    assert resolved == [str(test_path.resolve())]
