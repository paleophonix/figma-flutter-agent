"""Tests for diagnose opinion gating."""

from __future__ import annotations

from control_panel.repair.evaluation import (
    DIAGNOSE_MIN_CONFIDENCE,
    DiagnoseOpinion,
    evaluate_diagnose_opinion,
)
from control_panel.repair.ticket import FailureFamily, RepairTicket


def test_evaluate_proceeds_when_confident() -> None:
    ticket = RepairTicket(
        symptom_summary="emit bug",
        failure_family=FailureFamily.EMIT,
    )
    opinion = DiagnoseOpinion(confidence=0.6, recommended_law="FlexChildLaw")
    result = evaluate_diagnose_opinion(ticket, opinion)
    assert result.proceed is True
    assert result.opinion.recommended_law == "FlexChildLaw"


def test_evaluate_blocks_on_escalate() -> None:
    ticket = RepairTicket(
        symptom_summary="unknown",
        failure_family=FailureFamily.UNKNOWN,
        escalate_to_human=True,
    )
    opinion = DiagnoseOpinion(confidence=0.9, escalate=False)
    result = evaluate_diagnose_opinion(ticket, opinion)
    assert result.proceed is False


def test_evaluate_blocks_on_low_confidence() -> None:
    ticket = RepairTicket(
        symptom_summary="emit bug",
        failure_family=FailureFamily.EMIT,
    )
    opinion = DiagnoseOpinion(confidence=DIAGNOSE_MIN_CONFIDENCE - 0.01)
    result = evaluate_diagnose_opinion(ticket, opinion)
    assert result.proceed is False
