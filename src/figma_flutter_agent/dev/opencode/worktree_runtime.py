"""Poetry subprocess helpers for isolated repair worktrees."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from figma_flutter_agent.tools.ast_sidecar.commands import prebuilt_compiler_basename


def resolve_orchestrator_ast_compiler_path(orchestrator_root: Path) -> Path | None:
    """Return the orchestrator checkout prebuilt AST compiler when present.

    Repair git worktrees omit gitignored ``tools/bin/ast_compiler*`` binaries.
    Subprocesses should inherit the parent checkout binary via env instead of
    falling back to slow ``dart run`` inside the worktree.

    Args:
        orchestrator_root: Active agent repo root (wizard checkout).

    Returns:
        Resolved prebuilt path, or ``None`` when not built locally.
    """
    candidate = orchestrator_root / "tools" / "bin" / prebuilt_compiler_basename()
    if candidate.is_file():
        return candidate.resolve()
    return None


def isolated_poetry_env() -> dict[str, str]:
    """Return a subprocess env without parent venv activation bleed.

    ``RepairWorktreePoetryPythonLaw``: after dropping ``VIRTUAL_ENV``, Poetry on
    Windows may resolve ``python`` from ``WindowsApps`` stubs (exit 9009). Pin the
    orchestrator interpreter via ``POETRY_PYTHON`` / ``PYTHON`` so worktree
    ``poetry install`` and gates use the same runtime as the parent CLI.
    """
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("POETRY_ACTIVE", None)
    python_path = str(Path(sys.executable).resolve())
    env["POETRY_PYTHON"] = python_path
    env["PYTHON"] = python_path
    return env


def isolated_poetry_env_for_worktree(*, orchestrator_root: Path) -> dict[str, str]:
    """Poetry env for worktree subprocesses with orchestrator AST sidecar binary.

    Args:
        orchestrator_root: Wizard checkout root (not the isolated worktree).

    Returns:
        Subprocess environment for ``poetry -P <worktree>`` repair gates/regenerate.
    """
    env = isolated_poetry_env()
    if env.get("FIGMA_AST_COMPILER_PATH", "").strip():
        return env
    compiler = resolve_orchestrator_ast_compiler_path(orchestrator_root)
    if compiler is not None:
        env["FIGMA_AST_COMPILER_PATH"] = str(compiler)
    return env


def run_poetry_cmd(worktree: Path, *poetry_args: str, timeout: int = 600) -> tuple[int, str]:
    """Run a Poetry project command against an isolated repair worktree."""
    cmd = ["poetry", "-P", str(worktree.resolve()), *poetry_args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=isolated_poetry_env(),
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output[-8000:]


def run_poetry_run(worktree: Path, *run_args: str, timeout: int = 600) -> tuple[int, str]:
    """Run ``poetry run`` inside the repair worktree project."""
    return run_poetry_cmd(worktree, "run", *run_args, timeout=timeout)
