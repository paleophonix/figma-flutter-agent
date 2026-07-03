"""Tier-0 layout candidate scorer — shadow mode (Program 05 P0-4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

LayoutCandidateKind = Literal["preserve_stack", "row", "column", "wrap"]


@dataclass(frozen=True, slots=True)
class LayoutCandidateScore:
    """Score breakdown struct — not a single opaque float."""

    geometry_residual: float
    exceptional_offsets: float
    paint_order_penalty: float
    ownership_violations: float
    flutter_invalidity: float
    complexity_cost: float
    total: float


@dataclass(frozen=True, slots=True)
class LayoutCandidate:
    """One layout hypothesis candidate."""

    kind: LayoutCandidateKind
    score: LayoutCandidateScore


@dataclass(frozen=True, slots=True)
class LayoutCandidateAudit:
    """Shadow scorer output for ``layout_candidates.json``."""

    node_id: str
    candidates: tuple[LayoutCandidate, ...]
    abstained: bool


def _score_candidate(node: CleanDesignTreeNode, kind: LayoutCandidateKind) -> LayoutCandidateScore:
    child_count = len(node.children)
    complexity = float(max(0, child_count - 2))
    geometry_residual = 0.0 if kind == "preserve_stack" and node.type == NodeType.STACK else 1.0
    if kind == "row" and node.type == NodeType.ROW:
        geometry_residual = 0.0
    if kind == "column" and node.type == NodeType.COLUMN:
        geometry_residual = 0.0
    if kind == "wrap" and node.type == NodeType.WRAP:
        geometry_residual = 0.0
    ownership_violations = 0.0  # diagnostic-only in P0
    exceptional_offsets = 0.0
    paint_order_penalty = 0.0
    flutter_invalidity = 0.0 if child_count < 50 else 1.0
    total = (
        geometry_residual
        + exceptional_offsets
        + paint_order_penalty
        + ownership_violations
        + flutter_invalidity
        + complexity * 0.1
    )
    return LayoutCandidateScore(
        geometry_residual=geometry_residual,
        exceptional_offsets=exceptional_offsets,
        paint_order_penalty=paint_order_penalty,
        ownership_violations=ownership_violations,
        flutter_invalidity=flutter_invalidity,
        complexity_cost=complexity * 0.1,
        total=total,
    )


def score_layout_candidates_shadow(node: CleanDesignTreeNode) -> LayoutCandidateAudit:
    """Tier-0 scorer: preserve-stack, row, column, wrap only (shadow, no emit change)."""
    kinds: tuple[LayoutCandidateKind, ...] = ("preserve_stack", "row", "column", "wrap")
    candidates = tuple(
        LayoutCandidate(kind=kind, score=_score_candidate(node, kind)) for kind in kinds
    )
    if len(node.children) < 2:
        return LayoutCandidateAudit(node_id=node.id, candidates=candidates, abstained=True)
    best = min(candidates, key=lambda item: item.score.total)
    second = sorted(candidates, key=lambda item: item.score.total)[1]
    abstained = abs(best.score.total - second.score.total) < 0.05
    return LayoutCandidateAudit(node_id=node.id, candidates=candidates, abstained=abstained)
