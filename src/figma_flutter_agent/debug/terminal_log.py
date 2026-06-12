"""Append pipeline subprocess and analyzer output to ``<project>/.debug/logs/last.log``."""

from __future__ import annotations

from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from figma_flutter_agent.debug.paths import project_run_log_path

_project_dir: ContextVar[Path | None] = ContextVar("terminal_log_project", default=None)


def bind_terminal_log_session(project_dir: Path) -> None:
    """Bind run transcript logging to a Flutter project for this pipeline run."""
    _project_dir.set(project_dir.resolve())


def clear_terminal_log_session() -> None:
    """Clear the bound run log session."""
    _project_dir.set(None)


def bound_terminal_log_path() -> Path | None:
    """Return the run log path for the bound project, if any."""
    project = _project_dir.get()
    if project is None:
        return None
    return project_run_log_path(project)


def append_terminal_output(
    label: str,
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = None,
    project_dir: Path | None = None,
) -> Path | None:
    """Append one block to ``<project>/.debug/logs/last.log``.

    Args:
        label: Short command description (for example ``dart analyze``).
        stdout: Captured stdout text.
        stderr: Captured stderr text.
        exit_code: Optional child exit code.
        project_dir: Explicit Flutter project root; falls back to the bound session.

    Returns:
        Log file path when written, else ``None`` when no project is available.
    """
    project = project_dir.resolve() if project_dir is not None else _project_dir.get()
    if project is None:
        return None

    path = project_run_log_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).isoformat()
    chunks: list[str] = [f"\n--- {label} @ {stamp} ---\n"]
    if exit_code is not None:
        chunks.append(f"exit_code={exit_code}\n")
    if stdout:
        chunks.append(stdout if stdout.endswith("\n") else f"{stdout}\n")
    if stderr and stderr != stdout:
        chunks.append(stderr if stderr.endswith("\n") else f"{stderr}\n")

    with path.open("a", encoding="utf-8") as handle:
        handle.write("".join(chunks))
    return path
