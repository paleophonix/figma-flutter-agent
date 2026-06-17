"""Unit tests for RepairTicket schema and markdown rendering."""

from __future__ import annotations

from control_panel.repair.ticket import (
    FailureFamily,
    RepairEvidence,
    RepairTicket,
    SuspectedLayer,
    render_ticket_markdown,
    repair_ticket_output_spec,
)


def test_repair_ticket_roundtrip() -> None:
    ticket = RepairTicket(
        symptom_summary="Dart analyze failed on emit",
        failure_family=FailureFamily.EMIT,
        suspected_layers=[
            SuspectedLayer(layer="emitter", confidence=0.8, rationale="pre_emit mismatch"),
        ],
        evidence=[RepairEvidence(file="dart-errors.json", quote="syntax error")],
        layout_hazards=["unbounded height"],
        repair_scope="src/figma_flutter_agent/generator/",
    )
    data = ticket.model_dump()
    restored = RepairTicket.model_validate(data)
    assert restored.failure_family == FailureFamily.EMIT
    assert restored.suspected_layers[0].layer == "emitter"


def test_render_ticket_markdown_includes_summary() -> None:
    ticket = RepairTicket(
        symptom_summary="Overflow in column",
        failure_family=FailureFamily.IR,
        escalate_to_human=True,
        escalate_reason="ambiguous stack",
    )
    body = render_ticket_markdown(ticket, repair_job_id="repair_test123")
    assert "repair_test123" in body
    assert "Overflow in column" in body
    assert "Escalate to human" in body


def test_repair_ticket_output_spec() -> None:
    spec = repair_ticket_output_spec(strict=True)
    assert spec.name == "repair_ticket"
    assert "symptom_summary" in spec.schema["properties"]
