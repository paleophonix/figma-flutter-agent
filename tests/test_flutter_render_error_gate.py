"""Tests for wizard render-error capture and preview gate."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.dev.flutter_app_log import (
    FlutterRenderErrorCapture,
    is_render_error_line,
)


def test_is_render_error_line_detects_overflow() -> None:
    line = "A RenderFlex overflowed by 1.00 pixels on the right."
    assert is_render_error_line(line) is True


def test_is_render_error_line_ignores_info_logs() -> None:
    assert is_render_error_line("Launching lib/main.dart on Chrome in debug mode...") is False


def test_render_error_capture_accumulates_errors() -> None:
    captured: list[str] = []

    capture = FlutterRenderErrorCapture(sink=captured.append)
    capture.feed_flutter_line("A RenderFlex overflowed by 1.00 pixels on the right.")
    capture.feed_flutter_line("Launching lib/main.dart on Chrome in debug mode...")
    capture.stop()

    assert capture.has_errors is True
    assert len(capture.errors) == 1
    assert "overflowed" in capture.errors[0]


def test_last_log_overflow_sample_is_render_error() -> None:
    log_path = Path(".debug/limbo/food_details/last.log")
    if not log_path.is_file():
        return
    overflow_lines = [
        line
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if "overflowed" in line.lower()
    ]
    if not overflow_lines:
        return
    assert is_render_error_line(overflow_lines[0]) is True
