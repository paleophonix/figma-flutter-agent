"""Tests for capture passport helpers."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.capture_passport import (
    capture_failure_class,
    capture_passport_summary,
    flutter_capture_trusted,
)
from figma_flutter_agent.dev.opencode.failure_class import FailureClass


def test_flutter_capture_trusted_requires_explicit_true() -> None:
    assert flutter_capture_trusted({}) is False
    assert flutter_capture_trusted({"flutterCaptureOk": False}) is False
    assert flutter_capture_trusted({"flutterCaptureOk": True}) is True


def test_capture_failure_class_overflow() -> None:
    manifest = {"warnings": ["A RenderFlex overflowed by 1.5 pixels on the right."]}
    assert capture_failure_class(manifest) == FailureClass.PATCH_RUNTIME


def test_capture_failure_class_dart_error() -> None:
    manifest = {"warnings": ["lib/generated/login_layout.dart:42:9: Error: undefined name"]}
    assert capture_failure_class(manifest) == FailureClass.PATCH_CODE_EMIT


def test_capture_passport_summary_blocked() -> None:
    summary = capture_passport_summary(
        {
            "flutterCaptureOk": False,
            "warnings": ["A RenderFlex overflowed by 1.5 pixels on the right."],
        }
    )
    assert summary["capture_verified"] is False
    assert summary["capture_kind"] == "blocked"
    assert summary["failure_class"] == FailureClass.PATCH_RUNTIME.value
