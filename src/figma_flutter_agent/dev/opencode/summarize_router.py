"""Summarize routing and data_context handoff."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.dev.opencode.schema_gate import validate_step_output


@dataclass(frozen=True)
class SummarizeRoute:
    """Summarize publish routing."""

    blocked: bool
    publish_ticket: bool
    write_data_context: bool
    payload: dict[str, Any]


def route_summarize(
    review_payload: dict[str, Any],
    *,
    state_dir: Path,
    repair_root: Path,
    task_completed: bool,
    agent_payload: dict[str, Any] | None = None,
) -> SummarizeRoute:
    """Apply summarize routing rules from review decision."""
    decision = str(review_payload.get("decision") or "STOP").upper()
    publish = decision == "CONTINUE" and task_completed
    write_ctx = decision == "STOP" or not task_completed
    agent = agent_payload or {}
    payload = {
        "step": "summarize",
        "blocked": False,
        "review_decision": decision,
        "review_reason_code": review_payload.get("reason_code"),
        "task_completed": task_completed,
        "ticket": {
            "publish": publish,
            "language": "ru",
            "summary": agent.get("ticket_summary") or agent.get("ticketSummary"),
        },
        "dev": {
            "language": "en",
            "summary": agent.get("dev_summary") or agent.get("devSummary"),
        },
        "routing": {
            "ticket_destination": "local",
            "data_context_written": write_ctx,
        },
        "agent": {
            "session_id": agent.get("session_id"),
            "notes": agent.get("notes"),
        },
    }
    validate_step_output("summarize", payload)
    path = state_dir / "summarize.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if write_ctx:
        ctx_path = repair_root / "data_context.json"
        ctx_path.write_text(
            json.dumps(
                {
                    "review": review_payload,
                    "summarize": payload,
                    "resume_hint": "rerun wizard debug with prior data_context",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    reports = repair_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    dev_text = (
        str(payload["dev"].get("summary") or "").strip()
        or f"# Dev summary\n\ndecision={decision}\n"
    )
    (reports / "dev_summary.md").write_text(dev_text, encoding="utf-8")
    if publish:
        ticket_text = (
            str(payload["ticket"].get("summary") or "").strip()
            or "# Ticket summary (RU)\n\nTask completed.\n"
        )
        (reports / "ticket_summary.md").write_text(ticket_text, encoding="utf-8")

    return SummarizeRoute(
        blocked=False,
        publish_ticket=publish,
        write_data_context=write_ctx,
        payload=payload,
    )


def apply_review_overrides(
    review_payload: dict[str, Any],
    *,
    check_passed: bool,
    capture_passed: bool,
    case_mode: str,
    initial_gate_verdict: str | None = None,
) -> dict[str, Any]:
    """Orchestrator hard overrides for review CONTINUE."""
    original = dict(review_payload)
    decision = str(review_payload.get("decision") or "STOP").upper()
    if decision == "CONTINUE":
        if not check_passed:
            review_payload = {
                **review_payload,
                "decision": "LOOP",
                "reason_code": "CHECK_REGRESSION_AFTER_REVIEW",
                "route": "repair.retry",
            }
        elif case_mode == "SCREEN" and not capture_passed:
            review_payload = {
                **review_payload,
                "decision": "LOOP",
                "reason_code": "CAPTURE_GATE_FAILED",
                "route": "diagnose.refine",
            }
        elif (
            str(review_payload.get("decision", "")).upper() == "CONTINUE"
            and not capture_passed
            and initial_gate_verdict == FailureClass.CAPTURE_FAILED.value
        ):
            review_payload = {
                **review_payload,
                "decision": "LOOP",
                "reason_code": "CAPTURE_RUNTIME_NOT_VERIFIED",
                "route": "diagnose.refine",
            }
    if review_payload != original:
        review_payload = {
            **review_payload,
            "overridden": True,
            "override_reason": str(review_payload.get("reason_code") or "HARD_GATE"),
            "original_decision": original.get("decision"),
        }
    return review_payload


def persist_review_state(
    review_payload: dict[str, Any],
    *,
    state_dir: Path,
    chain: Any,
    loop_round: int,
) -> None:
    """Rewrite review executive JSON and reasoning chain after orchestrator overrides."""
    from figma_flutter_agent.dev.opencode.checkpoint import append_checkpoint
    from figma_flutter_agent.dev.opencode.step_runner import write_step_state

    write_step_state(state_dir, "review", review_payload)
    chain.append("review", review_payload)
    append_checkpoint(state_dir, step="review", loop_round=loop_round)
