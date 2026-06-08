"""Spec-23 report models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Spec23CriterionResult:
    """Result for a single section-23 acceptance criterion."""

    name: str
    passed: bool
    detail: str = ""


@dataclass
class Spec23Report:
    """Aggregated section-23 acceptance report."""

    criteria: list[Spec23CriterionResult] = field(default_factory=list)
    generation_mode: str = "llm-ir"

    @property
    def passed(self) -> bool:
        """Return True when every criterion passed."""
        return all(item.passed for item in self.criteria)
