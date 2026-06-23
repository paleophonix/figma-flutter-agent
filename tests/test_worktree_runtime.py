"""Tests for isolated repair worktree Poetry subprocess env."""

from __future__ import annotations

import sys
from pathlib import Path

from figma_flutter_agent.dev.opencode.worktree_runtime import (
    isolated_poetry_env,
    isolated_poetry_env_for_worktree,
    resolve_orchestrator_ast_compiler_path,
)
from figma_flutter_agent.tools.ast_sidecar.commands import prebuilt_compiler_basename


def test_isolated_poetry_env_pins_orchestrator_python(monkeypatch) -> None:
    """Poetry must not fall back to PATH stubs after venv env vars are cleared."""
    monkeypatch.setenv("VIRTUAL_ENV", r"C:\fake\parent-venv")
    monkeypatch.setenv("POETRY_ACTIVE", "1")
    monkeypatch.setenv("POETRY_PYTHON", r"C:\WindowsApps\python.exe")

    env = isolated_poetry_env()

    expected = str(Path(sys.executable).resolve())
    assert "VIRTUAL_ENV" not in env
    assert "POETRY_ACTIVE" not in env
    assert env["POETRY_PYTHON"] == expected
    assert env["PYTHON"] == expected


def test_resolve_orchestrator_ast_compiler_path_returns_prebuilt(tmp_path: Path) -> None:
    bin_dir = tmp_path / "tools" / "bin"
    bin_dir.mkdir(parents=True)
    compiler = bin_dir / prebuilt_compiler_basename()
    compiler.write_text("stub", encoding="utf-8")
    resolved = resolve_orchestrator_ast_compiler_path(tmp_path)
    assert resolved == compiler.resolve()


def test_isolated_poetry_env_for_worktree_inherits_orchestrator_compiler(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("FIGMA_AST_COMPILER_PATH", raising=False)
    bin_dir = tmp_path / "tools" / "bin"
    bin_dir.mkdir(parents=True)
    compiler = bin_dir / prebuilt_compiler_basename()
    compiler.write_text("stub", encoding="utf-8")
    env = isolated_poetry_env_for_worktree(orchestrator_root=tmp_path)
    assert env["FIGMA_AST_COMPILER_PATH"] == str(compiler.resolve())


def test_isolated_poetry_env_for_worktree_respects_existing_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    override = tmp_path / "custom.exe"
    override.write_text("stub", encoding="utf-8")
    monkeypatch.setenv("FIGMA_AST_COMPILER_PATH", str(override))
    env = isolated_poetry_env_for_worktree(orchestrator_root=tmp_path)
    assert env["FIGMA_AST_COMPILER_PATH"] == str(override)
