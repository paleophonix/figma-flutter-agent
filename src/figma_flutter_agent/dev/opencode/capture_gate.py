"""Visual capture gate with runId passport."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.capture_passport import (
    capture_failure_class,
    flutter_capture_trusted,
)
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
    require_pixel_diff: bool = False,
) -> CaptureGateResult:
    """Evaluate capture.json against passport and optional pixel-diff rules."""
    capture_path = debug_mirror / "capture.json"
    passed = False
    kind = "forensic"
    captured_run_id: str | None = None
    score: float | None = None
    score_parse_error: str | None = None
    failure_class: FailureClass | None = FailureClass.PATCH_VISUAL

    if capture_path.is_file():
        data = json.loads(capture_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            raw_score = data.get("changedRatio")
            if raw_score is None and isinstance(data.get("diff"), dict):
                raw_score = data["diff"].get("score")
            if raw_score is not None:
                try:
                    score = float(raw_score)
                except (TypeError, ValueError) as exc:
                    score_parse_error = str(exc)
                    failure_class = FailureClass.PATCH_VISUAL
            captured_run_id = str(data.get("captured_run_id") or data.get("runId") or "")
            if not flutter_capture_trusted(data):
                failure_class = capture_failure_class(data)
            elif (
                captured_run_id
                and captured_run_id == served_run_id
                and captured_run_id == committed_run_id
            ):
                kind = "verified"
                failure_class = None
                if score is not None and (score <= threshold or not require_pixel_diff):
                    passed = True
                elif score is None and not require_pixel_diff:
                    passed = True
            elif flutter_capture_trusted(data) and not require_pixel_diff:
                kind = "verified"
                failure_class = None
                passed = True
            else:
                failure_class = FailureClass.PATCH_VISUAL

    payload: dict[str, Any] = {
        "step": "capture",
        "passed": passed,
        "kind": kind,
        "captured_run_id": captured_run_id,
        "target_build_run_id": committed_run_id,
        "served_build_run_id": served_run_id,
        "failure_class": None if passed else failure_class.value if failure_class else None,
        "route": None if passed else "diagnose.refine",
        "diff": {
            "score": score,
            "threshold": threshold,
            "score_parse_error": score_parse_error,
        },
    }
    validate_step_output("capture", payload)
    out = state_dir / "capture.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return CaptureGateResult(passed=passed, kind=kind, payload=payload)
