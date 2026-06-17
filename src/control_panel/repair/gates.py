"""Deterministic ruff and pytest gates after build stage."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GateResult:
    """Outcome of post-build quality gates."""

    passed: bool
    ruff_ok: bool
    pytest_ok: bool
    ruff_output: str
    pytest_output: str
    touched_paths: tuple[str, ...]


def _run_cmd(cwd: Path, *args: str, timeout: int = 600) -> tuple[int, str]:
    result = subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output[-8000:]


def run_repair_gates(worktree: Path, *, touched_paths: list[str] | None = None) -> GateResult:
    """Run ruff and scoped pytest in the agent-repo worktree.

    Args:
        worktree: Repair git worktree root.
        touched_paths: Optional module paths to pass to pytest; defaults to tests/control_panel.

    Returns:
        GateResult with subprocess output tails.
    """
    paths = touched_paths or ["tests/control_panel"]
    ruff_code, ruff_out = _run_cmd(
        worktree,
        "poetry",
        "run",
        "ruff",
        "check",
        "src/figma_flutter_agent",
        "src/control_panel",
        "tests",
    )
    pytest_targets = [p for p in paths if p.strip()]
    if not pytest_targets:
        pytest_targets = ["tests/control_panel"]
    pytest_code, pytest_out = _run_cmd(
        worktree,
        "poetry",
        "run",
        "pytest",
        "-q",
        *pytest_targets,
    )
    return GateResult(
        passed=ruff_code == 0 and pytest_code == 0,
        ruff_ok=ruff_code == 0,
        pytest_ok=pytest_code == 0,
        ruff_output=ruff_out,
        pytest_output=pytest_out,
        touched_paths=tuple(pytest_targets),
    )
