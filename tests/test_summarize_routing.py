"""Tests for summarize routing."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.summarize_router import (
    apply_review_overrides,
    route_summarize,
)


def test_summarize_writes_dev_summary_on_loop(tmp_path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    repair = tmp_path / "repair"
    repair.mkdir()
    route = route_summarize(
        {"decision": "LOOP", "reason_code": "LAW_NOT_CLOSED"},
        state_dir=state,
        repair_root=repair,
        task_completed=False,
        agent_payload={"dev_summary": "cycle not closed"},
    )
    assert route.blocked is False
    assert route.publish_ticket is False
    assert route.write_data_context is True
    assert route.payload["review_decision"] == "LOOP"


def test_review_continue_coerced_without_capture() -> None:
    review = apply_review_overrides(
        {"decision": "CONTINUE", "reason_code": "REVIEW_OK"},
        check_passed=True,
        capture_passed=False,
        case_mode="SCREEN",
    )
    assert review["decision"] == "LOOP"
    assert review["reason_code"] == "CAPTURE_GATE_FAILED"
