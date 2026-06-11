"""Core types for the semantic classifier."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr, WidgetIrKind, WidgetIrNode
from figma_flutter_agent.schemas.ir_payloads import LlmClassificationHint


class SignalTier(StrEnum):
    """Detector signal priority tier."""

    PROPERTIES = "properties"
    ANATOMY = "anatomy"
    GEOMETRY = "geometry"


@dataclass(frozen=True)
class TierSignals:
    """Collected signals for one clean-tree node."""

    properties_score: float = 0.0
    anatomy_score: float = 0.0
    geometry_score: float = 0.0
    property_hits: dict[str, Any] = field(default_factory=dict)
    anatomy_hits: dict[str, Any] = field(default_factory=dict)
    geometry_hits: dict[str, Any] = field(default_factory=dict)
    overlay_signal: bool = False
    hard_reject_kinds: frozenset[WidgetIrKind] = frozenset()


@dataclass
class DetectorContext:
    """Inputs for a per-node semantic detector."""

    clean_node: CleanDesignTreeNode
    ir_node: WidgetIrNode
    clean_by_id: dict[str, CleanDesignTreeNode]
    screen_ir: ScreenIr
    signals: TierSignals
    confidence_threshold: float
    grey_zone_min: float
    llm_hint: LlmClassificationHint | None = None


@dataclass(frozen=True)
class Classification:
    """Detector output for one widget kind candidate."""

    kind: WidgetIrKind
    confidence: float
    winning_tier: SignalTier
    evidence: dict[str, Any] = field(default_factory=dict)


class Detector(Protocol):
    """Classifies a single ``WidgetIrKind`` from structural signals."""

    kind: WidgetIrKind

    def detect(self, ctx: DetectorContext) -> Classification | None:
        """Return a classification or None when signals do not match."""
