"""Tests for capture gate passport."""

from __future__ import annotations

import json

from figma_flutter_agent.dev.opencode.capture_gate import run_capture_gate


def test_capture_forensic_without_run_id(tmp_path) -> None:
    mirror = tmp_path / "debug"
    mirror.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    result = run_capture_gate(
        mirror,
        state_dir=state,
        served_run_id="run_a",
        committed_run_id="run_a",
    )
    assert result.kind == "forensic"
    assert result.passed is False


def test_capture_verified_pass(tmp_path) -> None:
    mirror = tmp_path / "debug"
    mirror.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    (mirror / "capture.json").write_text(
        json.dumps(
            {
                "captured_run_id": "run_a",
                "flutterCaptureOk": True,
                "changedRatio": 0.01,
            }
        ),
        encoding="utf-8",
    )
    result = run_capture_gate(
        mirror,
        state_dir=state,
        served_run_id="run_a",
        committed_run_id="run_a",
    )
    assert result.kind == "verified"
    assert result.passed is True


def test_capture_blocked_on_flutter_capture_ok_false(tmp_path) -> None:
    mirror = tmp_path / "debug"
    mirror.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    (mirror / "capture.json").write_text(
        json.dumps(
            {
                "flutterCaptureOk": False,
                "warnings": ["A RenderFlex overflowed by 1.5 pixels on the right."],
            }
        ),
        encoding="utf-8",
    )
    result = run_capture_gate(
        mirror,
        state_dir=state,
        served_run_id="run_a",
        committed_run_id="run_a",
    )
    assert result.passed is False
    assert result.kind == "forensic"
    assert result.payload["failure_class"] == "PATCH_RUNTIME"


def test_capture_runtime_pass_without_pixel_diff(tmp_path) -> None:
    mirror = tmp_path / "debug"
    mirror.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    (mirror / "capture.json").write_text(
        json.dumps({"flutterCaptureOk": True}),
        encoding="utf-8",
    )
    result = run_capture_gate(
        mirror,
        state_dir=state,
        served_run_id="run_a",
        committed_run_id="run_b",
        require_pixel_diff=False,
    )
    assert result.passed is True
    assert result.kind == "verified"
