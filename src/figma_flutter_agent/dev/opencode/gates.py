"""Deterministic ruff and pytest gates after repair build."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.observability.prometheus_metrics import inc_repair_gate


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
    """Run ruff and scoped pytest in the agent-repo worktree."""
    paths = touched_paths or ["tests/test_debug_pipeline_models.py"]
    ruff_code, ruff_out = _run_cmd(
        worktree,
        "poetry",
        "run",
        "ruff",
        "check",
        "src/figma_flutter_agent/dev/opencode",
        "src/figma_flutter_agent/debug/run_meta.py",
    )
    pytest_targets = [p for p in paths if p.strip()] or ["tests/test_debug_pipeline_models.py"]
    pytest_code, pytest_out = _run_cmd(
        worktree,
        "poetry",
        "run",
        "pytest",
        "-q",
        *pytest_targets,
    )
    inc_repair_gate("ruff", "pass" if ruff_code == 0 else "fail")
    inc_repair_gate("pytest", "pass" if pytest_code == 0 else "fail")
    return GateResult(
        passed=ruff_code == 0 and pytest_code == 0,
        ruff_ok=ruff_code == 0,
        pytest_ok=pytest_code == 0,
        ruff_output=ruff_out,
        pytest_output=pytest_out,
        touched_paths=tuple(pytest_targets),
    )
