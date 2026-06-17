"""Unit tests for diagnose opinion evaluation."""

from __future__ import annotations

import pytest

from control_panel.repair.evaluation import DiagnoseOpinion, evaluate_diagnose_opinions
from control_panel.repair.ticket import FailureFamily, RepairTicket


def test_evaluate_proceeds_with_consensus() -> None:
    ticket = RepairTicket(
        symptom_summary="emit bug",
        failure_family=FailureFamily.EMIT,
    )
    opinions = [
        DiagnoseOpinion(role="skeptic", confidence=0.6, recommended_law="FlexChildLaw"),
        DiagnoseOpinion(role="empiric", confidence=0.7, recommended_law="FlexChildLaw"),
    ]
    result = evaluate_diagnose_opinions(ticket, opinions)
    assert result.proceed_to_consilium is True
    assert result.mean_confidence == pytest.approx(0.65)


def test_evaluate_blocks_on_escalate() -> None:
    ticket = RepairTicket(
        symptom_summary="unknown",
        failure_family=FailureFamily.UNKNOWN,
        escalate_to_human=True,
    )
    opinions = [DiagnoseOpinion(role="devil", confidence=0.9, escalate=False)]
    result = evaluate_diagnose_opinions(ticket, opinions)
    assert result.proceed_to_consilium is False
