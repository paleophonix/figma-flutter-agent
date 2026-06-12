"""Corpus oracle gate result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from figma_flutter_agent.fixtures.screens_manifest import CorpusTier


@dataclass(frozen=True)
class ScreenOracleMetrics:
    """Measured oracle metrics for one fixture screen."""

    non_text_pixel_diff: float | None = None
    text_region_pixel_diff: float | None = None
    text_bounds_delta: float | None = None
    geometry_iou: float | None = None


@dataclass(frozen=True)
class ScreenOracleResult:
    """Oracle evaluation outcome for one manifest screen."""

    screen_id: str
    corpus_tier: CorpusTier
    skipped: bool = False
    skip_reason: str | None = None
    blocking_pass: bool = False
    advisory_pass: bool = True
    metrics: ScreenOracleMetrics = field(default_factory=ScreenOracleMetrics)
    failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON reports."""
        return {
            "screen_id": self.screen_id,
            "corpus_tier": self.corpus_tier,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "blocking_pass": self.blocking_pass,
            "advisory_pass": self.advisory_pass,
            "metrics": {
                "non_text_pixel_diff": self.metrics.non_text_pixel_diff,
                "text_region_pixel_diff": self.metrics.text_region_pixel_diff,
                "text_bounds_delta": self.metrics.text_bounds_delta,
                "geometry_iou": self.metrics.geometry_iou,
            },
            "failures": list(self.failures),
        }


@dataclass(frozen=True)
class PromotionCandidate:
    """Recommended fidelity promotion (evidence only; no manifest mutation)."""

    fixture_id: str
    screen_id: str
    kind: str
    current_tier: str
    recommend: bool
    metrics: dict[str, float | None]

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON reports."""
        return {
            "fixture_id": self.fixture_id,
            "screen_id": self.screen_id,
            "kind": self.kind,
            "current_tier": self.current_tier,
            "recommend": self.recommend,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class CorpusGateReport:
    """Aggregate corpus oracle gate report."""

    blocking_passed: bool
    full_corpus_passed: bool
    advisory_only_failures: int
    results: tuple[ScreenOracleResult, ...]
    promotion_candidates: tuple[PromotionCandidate, ...] = ()

    @property
    def passed(self) -> bool:
        """Deprecated alias for ``full_corpus_passed`` (includes advisory failures)."""
        return self.full_corpus_passed

    def blocking_results(self) -> tuple[ScreenOracleResult, ...]:
        """Return results for strict_pixel_blocking tier only."""
        return tuple(item for item in self.results if item.corpus_tier == "strict_pixel_blocking")

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON reports."""
        return {
            "blocking_passed": self.blocking_passed,
            "full_corpus_passed": self.full_corpus_passed,
            "advisory_only_failures": self.advisory_only_failures,
            "results": [item.to_dict() for item in self.results],
            "promotion_candidates": [item.to_dict() for item in self.promotion_candidates],
        }
