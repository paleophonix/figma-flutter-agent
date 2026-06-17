"""Deterministic evaluation of epistemic diagnostician outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from control_panel.repair.ticket import RepairTicket


class DiagnoseOpinion(BaseModel):
    """Structured output from one epistemic diagnostician."""

    role: str
    root_cause: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_law: str = ""
    escalate: bool = False


class EvaluationResult(BaseModel):
    """Aggregated evaluation before consilium."""

    opinions: list[DiagnoseOpinion]
    mean_confidence: float
    consensus_failure_family: str
    proceed_to_consilium: bool
    notes: str = ""


def evaluate_diagnose_opinions(
    ticket: RepairTicket,
    opinions: list[DiagnoseOpinion],
) -> EvaluationResult:
    """Score diagnostician opinions deterministically.

    Args:
        ticket: Context-stage repair ticket.
        opinions: One opinion per epistemic role.

    Returns:
        Evaluation summary used to gate consilium.
    """
    if not opinions:
        return EvaluationResult(
            opinions=[],
            mean_confidence=0.0,
            consensus_failure_family=ticket.failure_family.value,
            proceed_to_consilium=False,
            notes="No diagnostician opinions",
        )
    confidences = [op.confidence for op in opinions]
    mean_conf = sum(confidences) / len(confidences)
    escalate_any = any(op.escalate for op in opinions) or ticket.escalate_to_human
    proceed = mean_conf >= 0.35 and not escalate_any
    laws = [op.recommended_law for op in opinions if op.recommended_law]
    notes = f"roles={len(opinions)}; laws={len(set(laws))}"
    return EvaluationResult(
        opinions=opinions,
        mean_confidence=mean_conf,
        consensus_failure_family=ticket.failure_family.value,
        proceed_to_consilium=proceed,
        notes=notes,
    )
