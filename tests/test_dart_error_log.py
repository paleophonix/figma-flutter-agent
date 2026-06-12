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
from figma_flutter_agent.generator.dart.project_validation import validate_dart_project


def _payload_from_run_log(text: str) -> dict:
    return json.loads(text[text.index("{") :])


@pytest.fixture(autouse=True)
def _reset_dart_error_session() -> None:
    clear_dart_error_session()
    yield
    clear_dart_error_session()


def test_record_dart_analyze_failure_writes_run_log(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    bind_dart_error_session(run_id="abc123", feature_name="music_v2", project_dir=project)
    path = record_dart_analyze_failure(
        stage="write",
        detail="dart analyze reported issues",
        errors=("error - lib/main.dart:1:1 - Expected ';'.",),
        analyze_output="error - lib/main.dart:1:1 - Expected ';'.",
        extra={"analyzeScope": "generated_only"},
    )

    assert path is not None
    assert path == project / ".debug" / "logs" / "last.log"
    text = path.read_text(encoding="utf-8")
    assert "dart analyze (write)" in text
    payload = _payload_from_run_log(text)
    assert payload["runId"] == "abc123"
    assert payload["stage"] == "write"
    assert payload["featureName"] == "music_v2"
    assert payload["projectDir"] == project.resolve().as_posix()
    assert payload["errors"] == ["error - lib/main.dart:1:1 - Expected ';'."]
    assert payload["analyzeScope"] == "generated_only"
    assert payload["passed"] is False


def test_error_log_survives_path_and_exception_in_payload(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    bind_dart_error_session(run_id="rob08", project_dir=project)
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
    payload = _payload_from_run_log(path.read_text(encoding="utf-8"))
    assert payload["projectPath"] == "/tmp/project"
    assert payload["cause"] == "ValueError: boom"
    assert payload["nested"]["trace"] == "/tmp/trace.log"
    assert "truncated" in payload["analyzeOutput"]


def test_record_dart_analyze_failure_without_session_returns_none() -> None:
    assert record_dart_analyze_failure(stage="write", detail="failed") is None


def test_record_dart_analyze_failure_skips_passing_checks(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    bind_dart_error_session(run_id="pass1", project_dir=project)
    assert record_dart_analyze_failure(stage="write", detail="ok", passed=True) is None
    assert not (project / ".debug" / "logs" / "last.log").exists()


def test_update_dart_error_session_merges_fields(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    bind_dart_error_session(run_id="upd1", project_dir=project)
    update_dart_error_session(feature_name="home", project_dir=project)
    record_dart_analyze_failure(stage="llm_repair", detail="failed", attempt=2)

    log_path = bound_dart_error_log_path()
    assert log_path is not None
    payload = _payload_from_run_log(log_path.read_text(encoding="utf-8"))
    assert payload["featureName"] == "home"
    assert payload["projectDir"] == project.resolve().as_posix()
    assert payload["attempt"] == 2


def test_validate_dart_project_records_session_log_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "lib" / "generated" / "screen_layout.dart"
    target.parent.mkdir(parents=True)
    target.write_text("void main() {}", encoding="utf-8")
    bind_dart_error_session(run_id="val1", feature_name="screen", project_dir=tmp_path)

    with (
        patch(
            "figma_flutter_agent.generator.dart.project_validation.analyze._toolchain_executables",
            return_value=("/usr/bin/dart", "/usr/bin/flutter"),
        ),
        patch("figma_flutter_agent.generator.dart.project_validation.analyze.run_subprocess") as run,
        patch("figma_flutter_agent.generator.dart.project_validation.format.run_subprocess", run),
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
    assert log_path == tmp_path / ".debug" / "logs" / "last.log"
    payload = _payload_from_run_log(log_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "llm_repair"
    assert payload["attempt"] == 1
    assert payload["featureName"] == "screen"
    assert any("Unterminated string literal" in line for line in payload["errors"])
