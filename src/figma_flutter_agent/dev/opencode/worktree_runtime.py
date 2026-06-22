"""Poetry subprocess helpers for isolated repair worktrees."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def isolated_poetry_env() -> dict[str, str]:
    """Return a subprocess env without parent venv activation bleed."""
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("POETRY_ACTIVE", None)
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
