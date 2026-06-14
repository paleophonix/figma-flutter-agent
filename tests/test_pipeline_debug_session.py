"""Per-run ``.debug/<feature>/last.log`` reset and capture."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.debug.paths import project_run_log_path
from figma_flutter_agent.debug.session_reset import reset_pipeline_run_debug_dirs
from figma_flutter_agent.debug.terminal_log import (
    append_terminal_output,
    bind_terminal_log_session,
    clear_terminal_log_session,
)
from figma_flutter_agent.tools.process_run import run_subprocess

_FEATURE = "feedback"


def test_reset_pipeline_run_debug_dirs_clears_logs_and_legacy_dirs(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    run_log = project_run_log_path(project, _FEATURE)
    run_log.parent.mkdir(parents=True)
    run_log.write_text("old terminal\n", encoding="utf-8")
    legacy_terminal = project / ".debug" / "terminal" / "last.log"
    legacy_terminal.parent.mkdir(parents=True)
    legacy_terminal.write_text("legacy\n", encoding="utf-8")
    legacy_dart = project / ".debug" / "dart-errors" / "last.jsonl"
    legacy_dart.parent.mkdir(parents=True)
    legacy_dart.write_text("{}\n", encoding="utf-8")
    dart_errors = project_run_log_path(project, _FEATURE).parent / "dart-errors.json"
    dart_errors.write_text('{"events":[]}', encoding="utf-8")

    reset_pipeline_run_debug_dirs(project, _FEATURE)

    assert not run_log.is_file()
    assert not dart_errors.is_file()
    assert not legacy_terminal.parent.exists()
    assert not legacy_dart.parent.exists()


def test_run_subprocess_appends_to_bound_terminal_log(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    bind_terminal_log_session(project, _FEATURE)
    try:
        with patch(
            "figma_flutter_agent.tools.process_run.subprocess.Popen",
        ) as popen_mock:
            proc = popen_mock.return_value
            proc.poll.side_effect = [None, 0]
            proc.returncode = 0
            proc.communicate.return_value = ("hello stdout\n", "")
            run_subprocess(
                ["echo", "hello"],
                cwd=project,
                label="echo test",
                timeout_sec=5.0,
                log=False,
            )
    finally:
        clear_terminal_log_session()

    log_path = project_run_log_path(project, _FEATURE)
    assert log_path.is_file()
    text = log_path.read_text(encoding="utf-8")
    assert "echo test" in text
    assert "hello stdout" in text
    assert "exit_code=0" in text


def test_append_terminal_output_without_bind_is_noop(tmp_path: Path) -> None:
    clear_terminal_log_session()
    assert append_terminal_output("noop", stdout="x") is None
