"""Deterministic post-repair compiler check gate."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.capture_passport import (
    capture_failure_class,
    flutter_capture_trusted,
)
from figma_flutter_agent.dev.opencode.failure_class import (
    FailureClass,
    classify_check_route,
    same_root_hash,
)
from figma_flutter_agent.dev.opencode.schema_gate import validate_step_output
from figma_flutter_agent.dev.opencode.scope_enforcement import collect_plan_target_files

_ANALYZE_CLEAN_MARKERS = (
    "pre_write_analyze passed",
    "dart analyze: no issues",
    "analyze passed",
    "analyzer: 0 issues",
)
_GENERATED_ANALYZE_BLOCK = re.compile(
    r"--- dart analyze \(generated\)[^\n]* ---\s*\nexit_code=0\b",
    re.MULTILINE,
)
_PIPELINE_RUN_MARKERS = re.compile(
    r"(^|\n)(generate\b|--- dart analyze|pre_write_analyze)",
    re.IGNORECASE,
)
_ANALYZE_ERROR_LINE = re.compile(r"^\s*error\s+-", re.MULTILINE)
_TOOLCHAIN_FLAKE_MARKERS = (
    "timeout",
    "timed out",
    "toolchain",
    "connection reset",
    "temporarily unavailable",
)
_PATH_IN_ERROR = re.compile(r"([A-Za-z0-9_./\\-]+\.(?:dart|py))")


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
    if gates.get("skipped") and not repair_payload.get("salvaged"):
        return False
    touched = repair_payload.get("filesTouched") or []
    if not isinstance(touched, list) or not touched:
        return False
    touched_set = {str(p) for p in touched}
    compiler_touched = {path for path in touched_set if path.startswith("src/figma_flutter_agent/")}
    if repair_payload.get("salvaged"):
        return bool(compiler_touched)
    if not plan_payload:
        return False
    plan_targets = collect_plan_target_files(plan_payload)
    compiler_targets = {p for p in plan_targets if p.startswith("src/figma_flutter_agent/")}
    if not compiler_targets:
        return False
    return bool(compiler_targets.intersection(touched_set))


def _load_dart_errors(path: Path) -> list[Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [{"message": "dart-errors.json unreadable"}]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.get("errors") or data.get("events") or [])
    return []


def _safe_json_dict(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _log_tail_since_last_pipeline_run(text: str) -> str:
    """Return log suffix after the last generate/analyze marker."""
    matches = list(_PIPELINE_RUN_MARKERS.finditer(text))
    if not matches:
        return text
    return text[matches[-1].start() :]


def _log_text(debug_mirror: Path) -> str:
    path = debug_mirror / "last.log"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").lower()


def _generated_analyze_block_proves_clean(text: str) -> bool:
    """Return True when the latest generated analyze block exited cleanly."""
    matches = list(_GENERATED_ANALYZE_BLOCK.finditer(text))
    if not matches:
        return False
    start = matches[-1].end()
    tail = text[start:]
    next_block = tail.find("--- ")
    block_body = tail if next_block < 0 else tail[:next_block]
    return _ANALYZE_ERROR_LINE.search(block_body) is None


def _log_proves_analyze_clean(debug_mirror: Path) -> bool:
    text = _log_text(debug_mirror)
    tail = _log_tail_since_last_pipeline_run(text)
    if _generated_analyze_block_proves_clean(tail):
        return True
    return any(marker in tail for marker in _ANALYZE_CLEAN_MARKERS)


def _log_indicates_toolchain_flake(debug_mirror: Path) -> bool:
    text = _log_text(debug_mirror)
    return any(marker in text for marker in _TOOLCHAIN_FLAKE_MARKERS)


def _classify_dart_errors(
    errors: list[Any],
    *,
    plan_payload: dict[str, Any] | None,
) -> FailureClass:
    if not errors:
        return FailureClass.FRESH_OK
    compiler_targets: set[str] = set()
    if plan_payload:
        compiler_targets = {
            p
            for p in collect_plan_target_files(plan_payload)
            if p.startswith("src/figma_flutter_agent/")
        }
    if not compiler_targets:
        return FailureClass.PATCH_CODE_EMIT
    blob = json.dumps(errors, ensure_ascii=False).lower()
    for target in compiler_targets:
        token = target.split("/")[-1]
        if target.lower() in blob or token.lower() in blob:
            return FailureClass.PATCH_CODE_COMPILER
    for match in _PATH_IN_ERROR.findall(blob):
        normalized = match.replace("\\", "/")
        if normalized.startswith("src/figma_flutter_agent/"):
            return FailureClass.PATCH_CODE_COMPILER
    return FailureClass.PATCH_CODE_EMIT


def _classify_missing_dart_errors(debug_mirror: Path) -> FailureClass | None:
    """Return failure class when dart-errors.json is absent, or None if analyze is proven clean."""
    if _log_proves_analyze_clean(debug_mirror):
        return None
    if _log_indicates_toolchain_flake(debug_mirror):
        return FailureClass.TOOLCHAIN_FLAKE
    return FailureClass.UNKNOWN_BLOCKED


def run_check_gate(
    debug_mirror: Path,
    *,
    state_dir: Path,
    repair_payload: dict[str, Any] | None = None,
    plan_payload: dict[str, Any] | None = None,
    allow_stale_mirror_bypass: bool = False,
    require_flutter_capture: bool = False,
    fix_materialization_only: bool = False,
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
        require_flutter_capture: When true, require ``capture.json`` ``flutterCaptureOk``.

    Returns:
        CheckResult with route suitable for orchestrator dispatch.
    """
    if fix_materialization_only:
        root_hash = same_root_hash(
            failure_class=FailureClass.CANDIDATE_ONLY.value,
            normalized_stage="fix_materialization",
        )
        payload = {
            "step": "check",
            "passed": False,
            "failedStage": "emit_materialization",
            "failure_class": FailureClass.CANDIDATE_ONLY.value,
            "failureLayer": "emit",
            "route": "regenerate_required",
            "evidence": ["fix_materialization_only"],
            "same_root_hash": root_hash,
            "mirrorStale": True,
            "fix_skipped_mirror": True,
        }
        validate_step_output("check", payload)
        out = state_dir / "check.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return CheckResult(
            passed=False,
            failure_class=FailureClass.CANDIDATE_ONLY,
            route="regenerate_required",
            payload=payload,
        )

    if allow_stale_mirror_bypass and compiler_repair_verified(repair_payload, plan_payload):
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
            "route": "regenerate_required",
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
            route="regenerate_required",
            payload=payload,
        )

    dart_errors = debug_mirror / "dart-errors.json"
    failed_stage = "pre_write_analyze"
    failure = FailureClass.FRESH_OK
    passed = True
    evidence: list[str] = []

    if dart_errors.is_file():
        errors = _load_dart_errors(dart_errors)
        if errors:
            passed = False
            failure = _classify_dart_errors(errors, plan_payload=plan_payload)
            evidence.append("dart-errors.json")
    else:
        missing_class = _classify_missing_dart_errors(debug_mirror)
        if missing_class is not None:
            passed = False
            failure = missing_class
            failed_stage = (
                "toolchain" if failure == FailureClass.TOOLCHAIN_FLAKE else "pre_write_analyze"
            )
            evidence.append("dart-errors.json:missing")

    capture_path = debug_mirror / "capture.json"
    if passed and require_flutter_capture:
        if not capture_path.is_file():
            passed = False
            failure = FailureClass.CAPTURE_ARTIFACT_MISSING
            failed_stage = "flutter_capture"
            evidence.append("capture.json:missing")
        else:
            capture_manifest = _safe_json_dict(capture_path)
            if not flutter_capture_trusted(capture_manifest):
                passed = False
                failure = capture_failure_class(capture_manifest)
                failed_stage = "flutter_capture"
                evidence.append("capture.json")
                if failure == FailureClass.PATCH_RUNTIME:
                    failed_stage = "flutter_runtime"

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
        "failureLayer": (
            "compiler"
            if not passed and failure == FailureClass.PATCH_CODE_COMPILER
            else (
                "emit"
                if not passed and failure == FailureClass.PATCH_CODE_EMIT
                else ("capture" if not passed else None)
            )
        ),
        "route": route,
        "evidence": evidence,
        "same_root_hash": root_hash,
    }
    validate_step_output("check", payload)
    out = state_dir / "check.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return CheckResult(passed=passed, failure_class=failure, route=route, payload=payload)
