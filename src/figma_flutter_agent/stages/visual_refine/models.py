"""Data models for the LLM visual refine stage."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LlmVisualRefineStageResult:
    """Output of the visual refine loop."""

    planned_files: dict[str, str]
    warnings: list[str] = field(default_factory=list)
    refine_attempts: int = 0
    initial_changed_ratio: float | None = None
    final_changed_ratio: float | None = None
