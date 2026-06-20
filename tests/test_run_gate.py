"""Tests for Run Gate (M0)."""

from __future__ import annotations

import json

from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.debug.run_meta import write_run_meta
from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.dev.opencode.run_gate import evaluate_run_gate


def test_run_gate_fresh_ok(tmp_path) -> None:
    project = tmp_path / "demo_app"
    feature = "login"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "processed.json").write_text("{}", encoding="utf-8")
    (root / "last.log").write_text("ok\n", encoding="utf-8")
    (root / "screen.dart").write_text(
        "// FFA_RUN_ID: run_abc\n",
        encoding="utf-8",
    )
    write_run_meta(
        project,
        feature,
        pipeline_run_id="run_abc",
        writeback="committed",
        written_files=["lib/generated/login.dart"],
        committed_build_run_id="run_abc",
        analyze_passed=True,
    )
    (root / "capture.json").write_text(
        json.dumps({"flutterCaptureOk": True, "changedRatio": 0.01}),
        encoding="utf-8",
    )
    result = evaluate_run_gate(project, feature)
    assert result.verdict == FailureClass.FRESH_OK
    assert result.case_mode == "SCREEN"
    assert result.manifest_path.is_file()


def test_run_gate_rolled_back(tmp_path) -> None:
    project = tmp_path / "demo_app"
    feature = "login"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "processed.json").write_text("{}", encoding="utf-8")
    (root / "screen.dart").write_text("// candidate\n", encoding="utf-8")
    write_run_meta(
        project,
        feature,
        pipeline_run_id="run_fail",
        writeback="rollback",
        written_files=[],
        committed_build_run_id="run_prev",
    )
    result = evaluate_run_gate(project, feature)
    assert result.verdict == FailureClass.ROLLED_BACK
    assert result.case_mode == "FORENSIC"


def test_run_gate_no_serve_without_meta(tmp_path) -> None:
    project = tmp_path / "demo_app"
    feature = "login"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "processed.json").write_text("{}", encoding="utf-8")
    result = evaluate_run_gate(project, feature)
    assert result.verdict == FailureClass.NO_SERVE
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["verdict"] == "NO_SERVE"


def test_run_gate_capture_failed_routes_forensic(tmp_path) -> None:
    project = tmp_path / "demo_app"
    feature = "login"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "screen.dart").write_text("// FFA_RUN_ID: run_abc\n", encoding="utf-8")
    write_run_meta(
        project,
        feature,
        pipeline_run_id="run_abc",
        writeback="committed",
        written_files=["lib/generated/login.dart"],
        committed_build_run_id="run_abc",
        analyze_passed=True,
    )
    (root / "capture.json").write_text(
        json.dumps(
            {
                "flutterCaptureOk": False,
                "warnings": ["A RenderFlex overflowed by 1.5 pixels on the right."],
            }
        ),
        encoding="utf-8",
    )
    result = evaluate_run_gate(project, feature)
    assert result.verdict == FailureClass.CAPTURE_FAILED
    assert result.case_mode == "FORENSIC"
    assert result.agent_board == "forensic"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["capture_passport"]["capture_kind"] == "blocked"
