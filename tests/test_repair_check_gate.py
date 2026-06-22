"""Tests for deterministic repair check gate."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.dev.opencode.check import run_check_gate
from figma_flutter_agent.dev.opencode.failure_class import FailureClass


def test_check_missing_dart_errors_not_pass(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    state_dir = tmp_path / "state"
    mirror.mkdir()
    state_dir.mkdir()
    result = run_check_gate(mirror, state_dir=state_dir)
    assert not result.passed
    assert result.failure_class == FailureClass.UNKNOWN_BLOCKED
    assert "dart-errors.json:missing" in result.payload.get("evidence", [])


def test_check_missing_dart_errors_passes_with_analyze_log_marker(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    state_dir = tmp_path / "state"
    mirror.mkdir()
    state_dir.mkdir()
    (mirror / "last.log").write_text("pre_write_analyze passed\n", encoding="utf-8")
    result = run_check_gate(mirror, state_dir=state_dir)
    assert result.passed
    assert result.failure_class == FailureClass.FRESH_OK


def test_check_missing_dart_errors_passes_with_generated_analyze_exit_zero(
    tmp_path: Path,
) -> None:
    mirror = tmp_path / "mirror"
    state_dir = tmp_path / "state"
    mirror.mkdir()
    state_dir.mkdir()
    (mirror / "last.log").write_text(
        "\n".join(
            [
                "--- dart analyze (generated) (1/3) @ 2026-06-22T14:39:39+00:00 ---",
                "exit_code=0",
                "warning - lib/foo.dart:1:1 - Unused import. - unused_import",
                "19 issues found.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = run_check_gate(mirror, state_dir=state_dir)
    assert result.passed
    assert result.failure_class == FailureClass.FRESH_OK


def test_check_missing_dart_errors_blocks_when_generated_analyze_has_errors(
    tmp_path: Path,
) -> None:
    mirror = tmp_path / "mirror"
    state_dir = tmp_path / "state"
    mirror.mkdir()
    state_dir.mkdir()
    (mirror / "last.log").write_text(
        "\n".join(
            [
                "--- dart analyze (generated) @ 2026-06-22T14:39:39+00:00 ---",
                "exit_code=0",
                "error - lib/foo.dart:1:1 - Expected identifier. - expected_identifier",
            ]
        ),
        encoding="utf-8",
    )
    result = run_check_gate(mirror, state_dir=state_dir)
    assert not result.passed
    assert result.failure_class == FailureClass.UNKNOWN_BLOCKED


def test_check_toolchain_flake_on_timeout_log(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    state_dir = tmp_path / "state"
    mirror.mkdir()
    state_dir.mkdir()
    (mirror / "last.log").write_text("dart analyze timed out\n", encoding="utf-8")
    result = run_check_gate(mirror, state_dir=state_dir)
    assert not result.passed
    assert result.failure_class == FailureClass.TOOLCHAIN_FLAKE
    assert result.route == "check.retry"


def test_check_compiler_errors_route_repair_retry(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    state_dir = tmp_path / "state"
    mirror.mkdir()
    state_dir.mkdir()
    (mirror / "dart-errors.json").write_text(
        json.dumps(
            [
                {
                    "message": "error",
                    "location": {"file": "src/figma_flutter_agent/generator/foo.py"},
                }
            ]
        ),
        encoding="utf-8",
    )
    plan = {
        "steps": [
            {
                "targetFiles": ["src/figma_flutter_agent/generator/foo.py"],
                "tests": ["tests/test_foo.py"],
            }
        ]
    }
    result = run_check_gate(mirror, state_dir=state_dir, plan_payload=plan)
    assert not result.passed
    assert result.failure_class == FailureClass.PATCH_CODE_COMPILER
    assert result.route == "repair.retry"
