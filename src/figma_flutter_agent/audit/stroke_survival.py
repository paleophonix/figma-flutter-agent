"""Stroke survival audit pipeline (Program 07 P0-3)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from figma_flutter_agent.schemas import CleanDesignTreeNode


class StrokeSurvivalVerdict(StrEnum):
    PRESERVED = "preserved"
    BAKED = "baked"
    LOST = "lost"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class StrokeAuditRecord:
    node_id: str
    stage: str
    verdict: StrokeSurvivalVerdict
    detail: str = ""


def _node_has_stroke(node: CleanDesignTreeNode) -> bool:
    strokes = getattr(node, "strokes", None)
    return bool(strokes)


def audit_stroke_chain(tree: CleanDesignTreeNode) -> list[StrokeAuditRecord]:
    """Audit stroke facts across parser→export chain (read-only)."""
    records: list[StrokeAuditRecord] = []

    def walk(node: CleanDesignTreeNode, stage: str) -> None:
        if _node_has_stroke(node):
            verdict = (
                StrokeSurvivalVerdict.BAKED
                if node.render_boundary
                else StrokeSurvivalVerdict.PRESERVED
            )
            records.append(
                StrokeAuditRecord(
                    node_id=node.id,
                    stage=stage,
                    verdict=verdict,
                    detail="stroke present on clean tree node",
                ),
            )
        for child in node.children:
            walk(child, stage)

    walk(tree, "parser")
    return records


def stroke_audit_summary(records: list[StrokeAuditRecord]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.verdict.value] = counts.get(record.verdict.value, 0) + 1
    return {"counts": counts, "lost": [r.node_id for r in records if r.verdict == StrokeSurvivalVerdict.LOST]}
