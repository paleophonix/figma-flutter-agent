"""Structured semantic classification report schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ReportBucket = Literal[
    "accepted",
    "rejectedBelowThreshold",
    "rejectedByInvariant",
    "llmAnnotationUsed",
]


@dataclass(frozen=True)
class ReportNode:
    """One node outcome bucket entry."""

    figma_id: str
    kind: str | None
    confidence: float
    evidence: dict[str, object] = field(default_factory=dict)
    reject_reason: str | None = None


@dataclass
class SemanticClassificationReport:
    """Full classification report for debug and CI artifacts."""

    accepted: list[ReportNode] = field(default_factory=list)
    rejected_below_threshold: list[ReportNode] = field(default_factory=list)
    rejected_by_invariant: list[ReportNode] = field(default_factory=list)
    legacy_semantic_type_detected: list[str] = field(default_factory=list)
    name_signal_used: list[str] = field(default_factory=list)
    llm_annotation_used: list[ReportNode] = field(default_factory=list)

    def add(self, bucket: ReportBucket, node: ReportNode) -> None:
        """Append a node to the named bucket."""
        if bucket == "accepted":
            self.accepted.append(node)
        elif bucket == "rejectedBelowThreshold":
            self.rejected_below_threshold.append(node)
        elif bucket == "rejectedByInvariant":
            self.rejected_by_invariant.append(node)
        elif bucket == "llmAnnotationUsed":
            self.llm_annotation_used.append(node)

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON dump."""
        return {
            "accepted": [_node_dict(item) for item in self.accepted],
            "rejectedBelowThreshold": [_node_dict(item) for item in self.rejected_below_threshold],
            "rejectedByInvariant": [_node_dict(item) for item in self.rejected_by_invariant],
            "legacySemanticTypeDetected": list(self.legacy_semantic_type_detected),
            "nameSignalUsed": list(self.name_signal_used),
            "llmAnnotationUsed": [_node_dict(item) for item in self.llm_annotation_used],
            "acceptedCount": len(self.accepted),
            "totalDecisions": (
                len(self.accepted)
                + len(self.rejected_below_threshold)
                + len(self.rejected_by_invariant)
                + len(self.llm_annotation_used)
            ),
        }


def _node_dict(node: ReportNode) -> dict[str, object]:
    return {
        "figmaId": node.figma_id,
        "kind": node.kind,
        "confidence": node.confidence,
        "evidence": node.evidence,
        "rejectReason": node.reject_reason,
    }


@dataclass(frozen=True)
class ArbitrationOutcome:
    """Arbiter decision with report bucket."""

    kind: object | None
    confidence: float
    evidence: dict[str, object]
    payload: object | None
    bucket: ReportBucket | None
    reject_reason: str | None = None
    runner_up_kind: str | None = None
