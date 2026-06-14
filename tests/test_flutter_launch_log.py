"""Tests for Flutter launch transcript logging."""

from __future__ import annotations

import sys
from pathlib import Path

from figma_flutter_agent.debug.paths import project_run_log_path
from figma_flutter_agent.tools.process_run import run_interactive_subprocess, run_subprocess


def test_run_interactive_subprocess_appends_last_log(
    debug_agent_root: Path, tmp_path: Path
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    feature = "bank_home"
    if sys.platform == "win32":
        command = ["cmd", "/c", "echo flutter-run-line"]
    else:
        command = ["sh", "-c", "echo flutter-run-line"]

    result = run_interactive_subprocess(
        command,
        cwd=project,
        label="flutter run (chrome)",
        project_dir=project,
        feature_name=feature,
    )

    assert result.returncode == 0
    log_path = project_run_log_path(project, feature)
    text = log_path.read_text(encoding="utf-8")
    assert "flutter run (chrome)" in text
    assert "flutter-run-line" in text
    assert "exit_code=0" in text


def test_run_subprocess_forwards_log_context(debug_agent_root: Path, tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    feature = "bank_home"
    if sys.platform == "win32":
        command = ["cmd", "/c", "echo pub-get-ok"]
    else:
        command = ["sh", "-c", "echo pub-get-ok"]

    result = run_subprocess(
        command,
        cwd=project,
        label="flutter pub get",
        timeout_sec=30.0,
        project_dir=project,
        feature_name=feature,
    )

    assert result.returncode == 0
    log_path = project_run_log_path(project, feature)
    text = log_path.read_text(encoding="utf-8")
    assert "flutter pub get" in text
    assert "pub-get-ok" in text


def test_parse_vm_service_uri() -> None:
    from figma_flutter_agent.dev.flutter_app_log import parse_vm_service_uri

    line = "Debug service listening on ws://127.0.0.1:54321/ws"
    assert parse_vm_service_uri(line) == "ws://127.0.0.1:54321/ws"


def test_last_log_stream_section_writes_live_lines(
    debug_agent_root: Path, tmp_path: Path
) -> None:
    from figma_flutter_agent.debug.terminal_log import LastLogStreamSection

    project = tmp_path / "demo"
    project.mkdir()
    section = LastLogStreamSection(
        "flutter render errors",
        project_dir=project,
        feature_name="bank_home",
    )
    section.open()
    section.write_line("A RenderFlex overflowed by 42 pixels on the bottom.")
    text = section.path.read_text(encoding="utf-8")
    assert "flutter render errors" in text
    assert "overflowed" in text


def test_is_render_error_line_filters_noise() -> None:
    from figma_flutter_agent.dev.flutter_app_log import is_render_error_line

    assert is_render_error_line("A RenderFlex overflowed by 12 pixels on the right.")
    assert is_render_error_line("Another exception was thrown: Exception: boom")
    assert not is_render_error_line("DDC is about to load 652/652 scripts with pool size = 1000")
    assert not is_render_error_line("Launching lib/main.dart on Chrome in debug mode...")


def test_run_interactive_subprocess_invokes_stdout_callback(
    debug_agent_root: Path, tmp_path: Path
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    seen: list[str] = []
    if sys.platform == "win32":
        command = ["cmd", "/c", "echo callback-line"]
    else:
        command = ["sh", "-c", "echo callback-line"]

    run_interactive_subprocess(
        command,
        cwd=project,
        label="callback-test",
        on_stdout_line=seen.append,
    )

    assert seen == ["callback-line"]
