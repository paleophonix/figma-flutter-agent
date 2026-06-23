"""Shared capture passport helpers for Run Gate and capture gate."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from figma_flutter_agent.dev.opencode.failure_class import FailureClass

_DART_COMPILE_ERROR = re.compile(r"\.dart:\d+:\d+:\s*Error:", re.IGNORECASE)
_RENDERFLEX_OVERFLOW = re.compile(r"RenderFlex overflow", re.IGNORECASE)


class CaptureRunState(StrEnum):
    """Tristate capture passport for Run Gate routing."""

    NOT_RUN = "not_run"
    RAN_OK = "ran_ok"
    RAN_FAIL = "ran_fail"


def coerce_capture_manifest(data: Any) -> dict[str, Any]:
    """Return a dict from capture.json payload or empty dict."""
    if isinstance(data, dict):
        return data
    return {}


def capture_run_state(manifest: dict[str, Any]) -> CaptureRunState:
    """Classify whether Flutter capture ran and whether it succeeded."""
    if not manifest:
        return CaptureRunState.NOT_RUN
    if manifest.get("flutterCaptureOk") is True:
        return CaptureRunState.RAN_OK
    return CaptureRunState.RAN_FAIL


def flutter_capture_trusted(manifest: dict[str, Any]) -> bool:
    """Return True when ``capture.json`` attests a fresh Flutter PNG capture."""
    return capture_run_state(manifest) == CaptureRunState.RAN_OK


def capture_failure_class(manifest: dict[str, Any]) -> FailureClass:
    """Map a failed capture passport to a repair routing failure class."""
    warnings = manifest.get("warnings") or []
    texts = [str(item) for item in warnings if str(item).strip()]
    combined = "\n".join(texts)
    if _RENDERFLEX_OVERFLOW.search(combined):
        return FailureClass.PATCH_RUNTIME
    if any(_DART_COMPILE_ERROR.search(text) for text in texts):
        return FailureClass.PATCH_CODE_EMIT
    return FailureClass.PATCH_RUNTIME


def capture_passport_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    """Build a compact capture passport for orchestrator ``run_context``."""
    run_state = capture_run_state(manifest)
    trusted = run_state == CaptureRunState.RAN_OK
    warnings = manifest.get("warnings") or []
    warning_texts = [str(item) for item in warnings if str(item).strip()]
    capture_kind = {
        CaptureRunState.RAN_OK: "verified",
        CaptureRunState.RAN_FAIL: "blocked",
        CaptureRunState.NOT_RUN: "not_run",
    }[run_state]
    return {
        "flutterCaptureOk": manifest.get("flutterCaptureOk"),
        "capture_run_state": run_state.value,
        "capture_verified": trusted,
        "capture_kind": capture_kind,
        "changedRatio": manifest.get("changedRatio"),
        "warnings": warning_texts[:8],
        "failure_class": None if trusted else capture_failure_class(manifest).value,
    }
