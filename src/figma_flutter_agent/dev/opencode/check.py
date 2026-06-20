"""Deterministic post-repair compiler check gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.failure_class import (
    FailureClass,
    classify_check_route,
    same_root_hash,
)
from figma_flutter_agent.dev.opencode.schema_gate import validate_step_output


@dataclass(frozen=True)
class CheckResult:
    """Outcome of deterministic check gate."""

    passed: bool
    failure_class: FailureClass
    route: str
    payload: dict[str, Any]


def run_check_gate(debug_mirror: Path, *, state_dir: Path) -> CheckResult:
    """Evaluate compiler check from debug mirror artifacts."""
    dart_errors = debug_mirror / "dart-errors.json"
    failed_stage = "pre_write_analyze"
    failure = FailureClass.FRESH_OK
    passed = True
    evidence: list[str] = []

    if dart_errors.is_file():
        data = json.loads(dart_errors.read_text(encoding="utf-8"))
        errors: list[Any] = []
        if isinstance(data, list):
            errors = data
        elif isinstance(data, dict):
            errors = list(data.get("errors") or data.get("events") or [])
        if errors:
            passed = False
            failure = FailureClass.PATCH_CODE_EMIT
            evidence.append("dart-errors.json")

    route = "capture" if passed else classify_check_route(failure)
    root_hash = same_root_hash(
        failure_class=failure.value,
        normalized_stage=failed_stage,
    )
    payload: dict[str, Any] = {
        "step": "check",
        "passed": passed,
        "failedStage": None if passed else failed_stage,
        "failure_class": failure.value,
        "failureLayer": "emit" if not passed else None,
        "route": route,
        "evidence": evidence,
        "same_root_hash": root_hash,
    }
    validate_step_output("check", payload)
    out = state_dir / "check.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return CheckResult(passed=passed, failure_class=failure, route=route, payload=payload)
