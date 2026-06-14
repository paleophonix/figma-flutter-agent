"""Append pipeline subprocess and analyzer output to ``<project>/.debug/<feature>/last.log``."""

from __future__ import annotations

import threading
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from figma_flutter_agent.debug.paths import project_run_log_path

_project_dir: ContextVar[Path | None] = ContextVar("terminal_log_project", default=None)
_feature_name: ContextVar[str | None] = ContextVar("terminal_log_feature", default=None)


def bind_terminal_log_session(project_dir: Path, feature_name: str | None = None) -> None:
    """Bind run transcript logging to a Flutter project screen for this pipeline run."""
    _project_dir.set(project_dir.resolve())
    _feature_name.set(feature_name.strip() if feature_name else None)


def clear_terminal_log_session() -> None:
    """Clear the bound run log session."""
    _project_dir.set(None)
    _feature_name.set(None)


def bound_terminal_log_path() -> Path | None:
    """Return the run log path for the bound project screen, if any."""
    project = _project_dir.get()
    feature = _feature_name.get()
    if project is None or not feature:
        return None
    return project_run_log_path(project, feature)


def append_terminal_output(
    label: str,
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = None,
    project_dir: Path | None = None,
    feature_name: str | None = None,
) -> Path | None:
    """Append one block to ``<project>/.debug/<feature>/last.log``.

    Args:
        label: Short command description (for example ``dart analyze``).
        stdout: Captured stdout text.
        stderr: Captured stderr text.
        exit_code: Optional child exit code.
        project_dir: Explicit Flutter project root; falls back to the bound session.
        feature_name: Screen slug; falls back to the bound session.

    Returns:
        Log file path when written, else ``None`` when no project screen is available.
    """
    project = project_dir.resolve() if project_dir is not None else _project_dir.get()
    feature = (feature_name or _feature_name.get() or "").strip()
    if project is None or not feature:
        return None

    path = project_run_log_path(project, feature)
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


class LastLogStreamSection:
    """Append live lines to ``last.log`` under one labelled section."""

    def __init__(
        self,
        label: str,
        *,
        project_dir: Path,
        feature_name: str,
    ) -> None:
        self._label = label
        self._path = project_run_log_path(project_dir, feature_name)
        self._lock = threading.Lock()
        self._opened = False

    @property
    def path(self) -> Path:
        """Resolved ``last.log`` path for this section."""
        return self._path

    def open(self) -> Path | None:
        """Write the section header once and return the log path."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=UTC).isoformat()
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n--- {self._label} @ {stamp} ---\n")
        self._opened = True
        return self._path

    def write_line(self, line: str) -> None:
        """Append one runtime log line to the open section."""
        if not self._opened:
            return
        text = line.rstrip("\n")
        if not text:
            return
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(f"{text}\n")
