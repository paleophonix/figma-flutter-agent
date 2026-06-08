"""Repair scope models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyzeErrorLocation:
    """One analyzer diagnostic tied to a planned Dart file."""

    file_path: str
    line: int
    column: int
    message: str
    raw: str


@dataclass(frozen=True)
class RepairTarget:
    """One generation target included in a scoped repair request."""

    target: str
    widget_name: str | None
    code: str
    planned_path: str
    errors: tuple[str, ...]
    planned_excerpt: str


@dataclass(frozen=True)
class RepairScope:
    """Scoped repair context derived from analyzer output."""

    targets: tuple[RepairTarget, ...]
    unchanged_widget_names: tuple[str, ...] = ()
    screen_included: bool = False


@dataclass(frozen=True)
class RepairEnvironmentContext:
    """Placeholder values for the repair system prompt environment block."""

    analyze_errors: str
    code: str
    semantic_hint: str
    failed_attempts_history: str
    unchanged_widget_names: str
    cpi_supervisor_directive: str = "(none)"
