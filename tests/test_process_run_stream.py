"""Tests for streamed subprocess log throttling."""

from __future__ import annotations

from figma_flutter_agent.tools.process_run import (
    _flutter_test_progress_key,
    _should_log_stream_line,
)


def test_flutter_test_progress_key_extracts_stable_suffix() -> None:
    assert (
        _flutter_test_progress_key("00:22 +0: ChooseTopicScreen matches golden file")
        == "+0: ChooseTopicScreen matches golden file"
    )
    assert _flutter_test_progress_key("not flutter output") is None


def test_should_log_stream_line_throttles_identical_ticks() -> None:
    state: dict[str, object] = {}
    line = "00:10 +0: ChooseTopicScreen matches golden file"
    assert _should_log_stream_line(line, state) is True
    assert (
        _should_log_stream_line("00:11 +0: ChooseTopicScreen matches golden file", state) is False
    )
    assert _should_log_stream_line("00:12 +1: All tests passed!", state) is True


def test_should_log_stream_line_logs_non_progress_lines() -> None:
    state: dict[str, object] = {}
    assert _should_log_stream_line("Compilation failed", state) is True
    assert _should_log_stream_line("Another error line", state) is True
