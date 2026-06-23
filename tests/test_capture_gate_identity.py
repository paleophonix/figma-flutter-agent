"""Tests for capture gate build identity alignment."""

from __future__ import annotations

import json

from figma_flutter_agent.dev.opencode.build_identity import reevaluate_build_identity
from figma_flutter_agent.dev.opencode.capture_gate import run_capture_gate
from figma_flutter_agent.dev.opencode.run_gate import evaluate_run_gate


def _gate(tmp_path, feature: str = "login"):
    project = tmp_path / "demo_app"
    return evaluate_run_gate(project, feature)


def test_capture_gate_passes_when_ids_match_post_regenerate(tmp_path) -> None:
    mirror = tmp_path / "mirror"
    mirror.mkdir(parents=True)
    (mirror / "screen.dart").write_text("// FFA_RUN_ID: regen_run\n", encoding="utf-8")
    (mirror / "capture.json").write_text(
        json.dumps(
            {
                "flutterCaptureOk": True,
                "captured_run_id": "regen_run",
                "changedRatio": 0.01,
            }
        ),
        encoding="utf-8",
    )
    gate = _gate(tmp_path)
    identity = reevaluate_build_identity(
        mirror,
        project_dir=tmp_path / "demo_app",
        feature="login",
        initial_gate=gate,
        regenerate_payload={"passed": True, "run_id": "regen_run"},
    )
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    result = run_capture_gate(
        mirror,
        state_dir=tmp_path / "state",
        served_run_id=identity.served_run_id,
        committed_run_id=identity.committed_run_id,
        require_pixel_diff=True,
    )
    assert result.passed is True
    assert result.kind == "verified"


def test_reevaluate_identity_switches_to_screen_after_regen(tmp_path) -> None:
    project = tmp_path / "demo_app"
    feature = "login"
    gate = evaluate_run_gate(project, feature)
    mirror = tmp_path / "mirror"
    mirror.mkdir(parents=True)
    (mirror / "screen.dart").write_text("// FFA_RUN_ID: regen_run\n", encoding="utf-8")
    (mirror / "capture.json").write_text(
        json.dumps({"flutterCaptureOk": True, "captured_run_id": "regen_run"}),
        encoding="utf-8",
    )
    identity = reevaluate_build_identity(
        mirror,
        project_dir=project,
        feature=feature,
        initial_gate=gate,
        regenerate_payload={"passed": True, "run_id": "regen_run"},
    )
    assert identity.committed_run_id == "regen_run"
    assert identity.case_mode == "SCREEN"
    assert identity.refreshed_from_regenerate is True
