"""Visual capture gate with runId passport."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.dev.opencode.schema_gate import validate_step_output


@dataclass(frozen=True)
class CaptureGateResult:
    """Outcome of capture gate."""

    passed: bool
    kind: str
    payload: dict[str, Any]


def run_capture_gate(
    debug_mirror: Path,
    *,
    state_dir: Path,
    served_run_id: str,
    committed_run_id: str,
    threshold: float = 0.05,
) -> CaptureGateResult:
    """Evaluate capture.json against runId passport rules."""
    capture_path = debug_mirror / "capture.json"
    passed = False
    kind = "forensic"
    captured_run_id: str | None = None
    score: float | None = None

    if capture_path.is_file():
        data = json.loads(capture_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            score = data.get("changedRatio")
            if score is None and isinstance(data.get("diff"), dict):
                score = data["diff"].get("score")
            captured_run_id = str(data.get("captured_run_id") or data.get("runId") or "")
            if captured_run_id and captured_run_id == served_run_id == committed_run_id:
                kind = "verified"
            if kind == "verified" and score is not None and float(score) <= threshold:
                passed = True

    payload: dict[str, Any] = {
        "step": "capture",
        "passed": passed,
        "kind": kind,
        "captured_run_id": captured_run_id,
        "target_build_run_id": committed_run_id,
        "served_build_run_id": served_run_id,
        "failure_class": None if passed else FailureClass.PATCH_VISUAL.value,
        "route": None if passed else "diagnose.refine",
        "diff": {"score": score, "threshold": threshold},
    }
    validate_step_output("capture", payload)
    out = state_dir / "capture.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return CaptureGateResult(passed=passed, kind=kind, payload=payload)
