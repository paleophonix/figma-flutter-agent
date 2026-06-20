"""Shared capture passport helpers for Run Gate and capture gate."""

from __future__ import annotations

import re
from typing import Any

from figma_flutter_agent.dev.opencode.failure_class import FailureClass

_DART_COMPILE_ERROR = re.compile(r"\.dart:\d+:\d+:\s*Error:", re.IGNORECASE)
_RENDERFLEX_OVERFLOW = re.compile(r"RenderFlex overflow", re.IGNORECASE)


def coerce_capture_manifest(data: Any) -> dict[str, Any]:
    """Return a dict from capture.json payload or empty dict."""
    if isinstance(data, dict):
        return data
    return {}


def flutter_capture_trusted(manifest: dict[str, Any]) -> bool:
    """Return True when ``capture.json`` attests a fresh Flutter PNG capture."""
    if not manifest:
        return False
    return manifest.get("flutterCaptureOk") is True


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
    trusted = flutter_capture_trusted(manifest)
    warnings = manifest.get("warnings") or []
    warning_texts = [str(item) for item in warnings if str(item).strip()]
    return {
        "flutterCaptureOk": manifest.get("flutterCaptureOk"),
        "capture_verified": trusted,
        "capture_kind": "verified" if trusted else "blocked",
        "changedRatio": manifest.get("changedRatio"),
        "warnings": warning_texts[:8],
        "failure_class": None if trusted else capture_failure_class(manifest).value,
    }
