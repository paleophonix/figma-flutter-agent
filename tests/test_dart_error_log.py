import json
from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.dart_error_log import (
    bind_dart_error_session,
    bound_dart_error_log_path,
    clear_dart_error_session,
    record_dart_analyze_failure,
    update_dart_error_session,
)
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.validation import validate_dart_project


@pytest.fixture(autouse=True)
def _reset_dart_error_session() -> None:
    clear_dart_error_session()
    yield
    clear_dart_error_session()


def test_record_dart_analyze_failure_writes_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_dir = tmp_path / "logs" / "dart-errors"
    monkeypatch.setattr("figma_flutter_agent.dart_error_log.DART_ERRORS_DIR", log_dir)

    bind_dart_error_session(run_id="abc123", feature_name="music_v2", project_dir="/demo")
    path = record_dart_analyze_failure(
        stage="write",
        detail="dart analyze reported issues",
        errors=("error - lib/main.dart:1:1 - Expected ';'.",),
        analyze_output="error - lib/main.dart:1:1 - Expected ';'.",
        extra={"analyzeScope": "generated_only"},
    )

    assert path is not None
    assert path.parent == log_dir
    assert path.name.endswith("-abc123.jsonl")
    assert path.stem.rsplit("-", 1)[-1] == "abc123"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["runId"] == "abc123"
    assert payload["stage"] == "write"
    assert payload["featureName"] == "music_v2"
    assert payload["projectDir"] == "/demo"
    assert payload["errors"] == ["error - lib/main.dart:1:1 - Expected ';'."]
    assert payload["analyzeScope"] == "generated_only"
    assert payload["passed"] is False


def test_error_log_survives_path_and_exception_in_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_dir = tmp_path / "logs" / "dart-errors"
    monkeypatch.setattr("figma_flutter_agent.dart_error_log.DART_ERRORS_DIR", log_dir)

    bind_dart_error_session(run_id="rob08", project_dir=Path("/demo"))
    path = record_dart_analyze_failure(
        stage="llm_repair",
        detail="analyzer failed",
        errors=("error - broken.dart:1:1 - syntax",),
        analyze_output="x" * 20_000,
        extra={
            "projectPath": Path("/tmp/project"),
            "cause": ValueError("boom"),
            "nested": {"trace": Path("/tmp/trace.log")},
        },
    )

    assert path is not None
    payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["projectPath"] == "/tmp/project"
    assert payload["cause"] == "ValueError: boom"
    assert payload["nested"]["trace"] == "/tmp/trace.log"
    assert "truncated" in payload["analyzeOutput"]


def test_record_dart_analyze_failure_without_session_returns_none() -> None:
    assert record_dart_analyze_failure(stage="write", detail="failed") is None


def test_record_dart_analyze_failure_skips_passing_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_dir = tmp_path / "logs" / "dart-errors"
    monkeypatch.setattr("figma_flutter_agent.dart_error_log.DART_ERRORS_DIR", log_dir)

    bind_dart_error_session(run_id="pass1")
    assert record_dart_analyze_failure(stage="write", detail="ok", passed=True) is None
    assert list(log_dir.glob("*.jsonl")) == []


def test_update_dart_error_session_merges_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_dir = tmp_path / "logs" / "dart-errors"
    monkeypatch.setattr("figma_flutter_agent.dart_error_log.DART_ERRORS_DIR", log_dir)

    bind_dart_error_session(run_id="upd1", project_dir="/old")
    update_dart_error_session(feature_name="home", project_dir="/new")
    record_dart_analyze_failure(stage="llm_repair", detail="failed", attempt=2)

    log_path = bound_dart_error_log_path()
    assert log_path is not None
    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["featureName"] == "home"
    assert payload["projectDir"] == "/new"
    assert payload["attempt"] == 2


def test_validate_dart_project_records_session_log_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_dir = tmp_path / "logs" / "dart-errors"
    monkeypatch.setattr("figma_flutter_agent.dart_error_log.DART_ERRORS_DIR", log_dir)

    target = tmp_path / "lib" / "generated" / "screen_layout.dart"
    target.parent.mkdir(parents=True)
    target.write_text("void main() {}", encoding="utf-8")
    bind_dart_error_session(run_id="val1", feature_name="screen")

    with (
        patch(
            "figma_flutter_agent.generator.validation._toolchain_executables",
            return_value=("/usr/bin/dart", "/usr/bin/flutter"),
        ),
        patch("figma_flutter_agent.generator.validation.run_subprocess") as run,
    ):
        run.side_effect = [
            type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            type(
                "R",
                (),
                {
                    "returncode": 3,
                    "stdout": "error - screen_layout.dart:1:1 - Unterminated string literal.",
                    "stderr": "",
                },
            )(),
        ]
        with pytest.raises(GenerationError):
            validate_dart_project(
                tmp_path,
                analyze_scope="generated_only",
                relative_paths=["lib/generated/screen_layout.dart"],
                analyze_stage="llm_repair",
                analyze_attempt=1,
            )

    log_path = bound_dart_error_log_path()
    assert log_path is not None and log_path.is_file()
    assert log_path.name.endswith("-val1.jsonl")
    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["stage"] == "llm_repair"
    assert payload["attempt"] == 1
    assert payload["featureName"] == "screen"
    assert any("Unterminated string literal" in line for line in payload["errors"])
