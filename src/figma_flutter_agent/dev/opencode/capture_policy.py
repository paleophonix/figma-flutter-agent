"""Repair pipeline capture proof policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.config.settings import Settings

CAPTURE_VERIFY_TERMINAL_REASONS: frozenset[str] = frozenset(
    {
        "CAPTURE_DISABLED",
        "REPAIR_CAPTURE_DISABLED",
    }
)


def repair_proof_capture_enabled(settings: Settings) -> bool:
    """Return whether the repair pipeline may run Flutter capture verify.

    ``RepairProofCaptureLaw``: when ``debug_pipeline.check_flutter_capture_verify``
    is enabled, post-repair capture proof is mandatory even if ``agent.dev.debug_capture``
    is false (that flag only gates generate-time capture, not repair closure).

    Args:
        settings: Loaded agent settings.

    Returns:
        True when repair may invoke ``run_capture_verify``.
    """
    if settings.agent.dev.debug_capture:
        return True
    return bool(settings.agent.debug_pipeline.check_flutter_capture_verify)


def capture_verify_failure_is_terminal(payload: dict[str, Any]) -> bool:
    """Return whether a capture verify failure cannot be fixed by retrying produce.

    ``CaptureVerifyNoopStopLaw``: when capture proof is disabled at execution time,
    re-routing to ``capture.verify`` only burns budget without producing artifacts.
    """
    return str(payload.get("reason_code") or "") in CAPTURE_VERIFY_TERMINAL_REASONS


def prepare_repair_capture_resume(
    *,
    phase_entry: str,
    chain_steps: dict[str, Any],
    state_dir: Path,
    loop_state: Any,
    run_context: dict[str, Any],
) -> None:
    """Apply resume hints for capture produce after infra noop or missing artifacts.

    ``RepairCaptureResumeLaw``: after ``CAPTURE_DISABLED`` or missing ``capture.json``,
    force one capture verify on the next check entry and clear stale produce budgets.
    """
    from figma_flutter_agent.dev.opencode.failure_class import FailureClass

    if phase_entry not in {"check", "regenerate", "capture_verify"}:
        return

    check = chain_steps.get("check")
    if isinstance(check, dict) and not check.get("passed"):
        failure = str(check.get("failure_class") or "")
        if failure == FailureClass.CAPTURE_ARTIFACT_MISSING.value:
            run_context["_force_capture_verify"] = True

    verify_path = state_dir / "capture_verify.json"
    if verify_path.is_file():
        try:
            payload = json.loads(verify_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and capture_verify_failure_is_terminal(payload):
            loop_state.capture_produce_attempts = 0
            loop_state.root_hash_counts.clear()
            loop_state.last_root_hash = ""
            loop_state.last_root_improved = False
            run_context["_force_capture_verify"] = True
