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
from figma_flutter_agent.dev.opencode.scope_enforcement import collect_plan_target_files


@dataclass(frozen=True)
class CheckResult:
    """Outcome of deterministic check gate."""

    passed: bool
    failure_class: FailureClass
    route: str
    payload: dict[str, Any]


def compiler_repair_verified(
    repair_payload: dict[str, Any] | None,
    plan_payload: dict[str, Any] | None,
) -> bool:
    """Return True when repair proved a compiler-layer change via gates, not mirror."""
    if not repair_payload or repair_payload.get("skipped"):
        return False
    gates = repair_payload.get("gates")
    if not isinstance(gates, dict) or not gates.get("passed"):
        return False
    touched = repair_payload.get("filesTouched") or []
    if not isinstance(touched, list) or not touched:
        return False
    if not plan_payload:
        return False
    plan_targets = collect_plan_target_files(plan_payload)
    compiler_targets = {p for p in plan_targets if p.startswith("src/figma_flutter_agent/")}
    if not compiler_targets:
        return False
    touched_set = {str(p) for p in touched}
    return bool(compiler_targets.intersection(touched_set))


def run_check_gate(
    debug_mirror: Path,
    *,
    state_dir: Path,
    repair_payload: dict[str, Any] | None = None,
    plan_payload: dict[str, Any] | None = None,
    allow_stale_mirror_bypass: bool = False,
) -> CheckResult:
    """Evaluate compiler check from debug mirror artifacts.

    When ``allow_stale_mirror_bypass`` is True and repair already verified
    compiler-layer changes, the frozen screen ``dart-errors.json`` mirror is
    ignored. Prefer re-running :func:`run_regenerate_after_compiler_repair` so
    check reads a fresh mirror instead of bypassing.

    Args:
        debug_mirror: Copied ``.debug/<project>/<feature>/`` bundle in the worktree.
        state_dir: ``.repair/state`` directory for ``check.json``.
        repair_payload: Latest repair step output, if any.
        plan_payload: Validated plan used for repair scope and gates.
        allow_stale_mirror_bypass: Skip stale mirror when compiler repair is proven.

    Returns:
        CheckResult with route suitable for orchestrator dispatch.
    """
    if (
        allow_stale_mirror_bypass
        and compiler_repair_verified(repair_payload, plan_payload)
    ):
        root_hash = same_root_hash(
            failure_class=FailureClass.FRESH_OK.value,
            normalized_stage="repair_gates",
        )
        payload: dict[str, Any] = {
            "step": "check",
            "passed": True,
            "failedStage": None,
            "failure_class": FailureClass.FRESH_OK.value,
            "failureLayer": None,
            "route": "capture",
            "evidence": [],
            "same_root_hash": root_hash,
            "verifiedBy": "repair_gates",
            "mirrorStale": True,
        }
        validate_step_output("check", payload)
        out = state_dir / "check.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return CheckResult(
            passed=True,
            failure_class=FailureClass.FRESH_OK,
            route="capture",
            payload=payload,
        )

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
    payload = {
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
