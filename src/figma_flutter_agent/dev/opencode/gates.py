"""Deterministic ruff and pytest gates after repair build."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.dev.opencode.worktree_runtime import run_poetry_cmd
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
    skipped: bool = False


def skipped_repair_gate_result(
    *,
    touched_paths: tuple[str, ...] = (),
) -> GateResult:
    """Return a passing gate result when repair made no compiler edits."""
    return GateResult(
        passed=True,
        ruff_ok=True,
        pytest_ok=True,
        ruff_output="",
        pytest_output="",
        touched_paths=touched_paths,
        skipped=True,
    )


def _run_poetry_cmd(worktree: Path, *poetry_args: str, timeout: int = 600) -> tuple[int, str]:
    """Run a Poetry project command against an isolated repair worktree."""
    return run_poetry_cmd(worktree, *poetry_args, timeout=timeout)


def _run_worktree_poetry_run(worktree: Path, *run_args: str, timeout: int = 600) -> tuple[int, str]:
    """Run ``poetry run`` inside the repair worktree project."""
    return _run_poetry_cmd(worktree, "run", *run_args, timeout=timeout)


def ensure_worktree_poetry_env(worktree: Path) -> None:
    """Install Poetry dev dependencies when the worktree venv cannot import test deps."""
    if not (worktree / "pyproject.toml").is_file():
        return
    probe_code, _ = _run_worktree_poetry_run(
        worktree,
        "python",
        "-c",
        "import prometheus_client",
        timeout=120,
    )
    if probe_code == 0:
        return
    install_code, install_out = _run_poetry_cmd(
        worktree,
        "install",
        "--with",
        "dev",
        "--no-interaction",
        timeout=900,
    )
    if install_code != 0:
        msg = f"poetry install failed in repair worktree: {install_out.strip()}"
        raise RuntimeError(msg)


def _split_gate_paths(touched_paths: list[str]) -> tuple[list[str], list[str]]:
    ruff_paths: list[str] = []
    pytest_paths: list[str] = []
    for raw in touched_paths:
        path = raw.strip().replace("\\", "/")
        if not path:
            continue
        if path.startswith("tests/"):
            pytest_paths.append(path)
        elif path.startswith("src/figma_flutter_agent/"):
            ruff_paths.append(path)
    if not ruff_paths:
        ruff_paths = ["src/figma_flutter_agent/dev/opencode"]
    if not pytest_paths:
        pytest_paths = ["tests/test_debug_pipeline_models.py"]
    return sorted(set(ruff_paths)), sorted(set(pytest_paths))


def _worktree_absolute_gate_paths(worktree: Path, paths: list[str]) -> list[str]:
    """Resolve repo-relative gate targets to absolute paths for Poetry subprocesses.

    When the orchestrator runs from the parent agent repo, ``poetry -P <worktree>``
    loads the worktree package but still resolves CLI arguments against the parent
    working directory. Absolute paths keep ruff/pytest pointed at worktree files.
    """
    root = worktree.resolve()
    absolute: list[str] = []
    for raw in paths:
        candidate = Path(raw)
        if candidate.is_absolute():
            absolute.append(str(candidate))
            continue
        absolute.append(str((root / raw).resolve()))
    return absolute


def run_repair_gates(worktree: Path, *, touched_paths: list[str] | None = None) -> GateResult:
    """Run ruff and scoped pytest in the agent-repo worktree."""
    ensure_worktree_poetry_env(worktree)
    paths = touched_paths or ["tests/test_debug_pipeline_models.py"]
    ruff_targets, pytest_targets = _split_gate_paths(paths)
    ruff_args = _worktree_absolute_gate_paths(worktree, ruff_targets)
    pytest_args = _worktree_absolute_gate_paths(worktree, pytest_targets)
    ruff_code, ruff_out = _run_worktree_poetry_run(
        worktree,
        "ruff",
        "check",
        *ruff_args,
    )
    pytest_code, pytest_out = _run_worktree_poetry_run(
        worktree,
        "pytest",
        "-q",
        *pytest_args,
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
