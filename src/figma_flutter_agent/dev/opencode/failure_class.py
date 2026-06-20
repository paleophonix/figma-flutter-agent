"""Unified failure taxonomy for Run Gate, check, capture, and review routing."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any


class FailureClass(StrEnum):
    """Canonical failure classes (single source of truth)."""

    FRESH_OK = "FRESH_OK"
    ROLLED_BACK = "ROLLED_BACK"
    STALE_CAPTURE = "STALE_CAPTURE"
    NO_SERVE = "NO_SERVE"
    CANDIDATE_ONLY = "CANDIDATE_ONLY"
    PATCH_CODE_EMIT = "PATCH_CODE_EMIT"
    PATCH_CODE_COMPILER = "PATCH_CODE_COMPILER"
    PATCH_RUNTIME = "PATCH_RUNTIME"
    PATCH_VISUAL = "PATCH_VISUAL"
    TOOLCHAIN_FLAKE = "TOOLCHAIN_FLAKE"
    INFRA_HARD = "INFRA_HARD"
    REVIEW_REJECTED = "REVIEW_REJECTED"
    REVIEW_STOP = "REVIEW_STOP"
    UNKNOWN_BLOCKED = "UNKNOWN_BLOCKED"


RUN_GATE_VERDICTS: frozenset[FailureClass] = frozenset(
    {
        FailureClass.FRESH_OK,
        FailureClass.ROLLED_BACK,
        FailureClass.STALE_CAPTURE,
        FailureClass.NO_SERVE,
        FailureClass.CANDIDATE_ONLY,
        FailureClass.UNKNOWN_BLOCKED,
    },
)

FORENSIC_VERDICTS: frozenset[FailureClass] = frozenset(
    {
        FailureClass.ROLLED_BACK,
        FailureClass.STALE_CAPTURE,
        FailureClass.CANDIDATE_ONLY,
        FailureClass.NO_SERVE,
        FailureClass.UNKNOWN_BLOCKED,
    },
)


def same_root_hash(
    *,
    failure_class: str,
    law_id: str = "",
    owning_layer: str = "",
    normalized_stage: str = "",
    normalized_component_kind: str = "",
) -> str:
    """Hash failure identity for loop budgets (law+layer root, not symptom text)."""
    payload = {
        "failure_class": failure_class,
        "law_id": law_id,
        "owning_layer": owning_layer,
        "normalized_stage": normalized_stage,
        "normalized_component_kind": normalized_component_kind,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()
    return f"sha256:{digest[:16]}"


def classify_check_route(failure_class: FailureClass) -> str:
    """Map check failure class to orchestrator route."""
    routes: dict[FailureClass, str] = {
        FailureClass.PATCH_CODE_EMIT: "fix",
        FailureClass.PATCH_CODE_COMPILER: "repair.retry",
        FailureClass.PATCH_RUNTIME: "diagnose.refine",
        FailureClass.PATCH_VISUAL: "diagnose.refine",
        FailureClass.ROLLED_BACK: "forensic",
        FailureClass.TOOLCHAIN_FLAKE: "check.retry",
        FailureClass.INFRA_HARD: "stop",
        FailureClass.FRESH_OK: "capture",
    }
    return routes.get(failure_class, "stop")


def case_mode_for_verdict(verdict: FailureClass) -> str:
    """Return SCREEN or FORENSIC for Run Gate verdict."""
    if verdict == FailureClass.FRESH_OK:
        return "SCREEN"
    if verdict in FORENSIC_VERDICTS:
        return "FORENSIC"
    return "BLOCKED"


def agent_board_for_case_mode(case_mode: str) -> str:
    """Map case_mode to agent board name."""
    if case_mode == "FORENSIC":
        return "forensic"
    return "screen"


def coerce_dict(value: Any) -> dict[str, Any]:
    """Return a dict from JSON object or empty dict."""
    if isinstance(value, dict):
        return value
    return {}
