"""Deterministic gating for a single diagnose opinion."""

from __future__ import annotations

from pydantic import BaseModel, Field

from control_panel.repair.ticket import RepairTicket

DIAGNOSE_MIN_CONFIDENCE = 0.35


class DiagnoseOpinion(BaseModel):
    """Structured output from the diagnose stage."""

    role: str = "diagnose"
    root_cause: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_law: str = ""
    escalate: bool = False


class DiagnoseGateResult(BaseModel):
    """Whether repair may continue after diagnose."""

    opinion: DiagnoseOpinion
    proceed: bool
    notes: str = ""


def evaluate_diagnose_opinion(ticket: RepairTicket, opinion: DiagnoseOpinion) -> DiagnoseGateResult:
    """Gate plan/build when diagnose is low-confidence or escalates.

    Args:
        ticket: Context-stage repair ticket.
        opinion: Single diagnose-stage opinion.

    Returns:
        Gate result used before plan.
    """
    if opinion.escalate or ticket.escalate_to_human:
        return DiagnoseGateResult(
            opinion=opinion,
            proceed=False,
            notes="escalate",
        )
    if opinion.confidence < DIAGNOSE_MIN_CONFIDENCE:
        return DiagnoseGateResult(
            opinion=opinion,
            proceed=False,
            notes=f"confidence below {DIAGNOSE_MIN_CONFIDENCE}",
        )
    law_note = opinion.recommended_law or "no law"
    return DiagnoseGateResult(
        opinion=opinion,
        proceed=True,
        notes=f"law={law_note}",
    )
