"""Tests for streamed subprocess log throttling."""

from __future__ import annotations

from figma_flutter_agent.tools.process_run import (
    _flutter_test_progress_key,
    _should_log_stream_line,
    is_noisy_subprocess_stream_line,
    summarize_subprocess_output,
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


def test_is_noisy_subprocess_stream_line_filters_stack_and_render_dump() -> None:
    assert is_noisy_subprocess_stream_line(
        "#30     RenderProxyBoxMixin.performLayout (package:flutter/src/rendering/proxy_box.dart:118:18)"
    )
    assert is_noisy_subprocess_stream_line("  creator: Column ← Expanded ← Column")
    assert is_noisy_subprocess_stream_line("  parentData: offset=Offset(0.0, 0.0); flex=1")
    assert is_noisy_subprocess_stream_line("<asynchronous suspension>")
    assert is_noisy_subprocess_stream_line(
        "(elided 7 frames from class _AssertionError, dart:async, and package:stack_trace)"
    )
    assert not is_noisy_subprocess_stream_line(
        "RenderFlex children have non-zero flex but incoming height constraints are unbounded."
    )
    assert not is_noisy_subprocess_stream_line(
        "The relevant error-causing widget was:"
    )
    assert not is_noisy_subprocess_stream_line(
        "  Column:file:///E:/demo/lib/generated/login_layout.dart:24:297"
    )


def test_should_log_stream_line_dedupes_exception_banners() -> None:
    state: dict[str, object] = {}
    banner = "══╡ EXCEPTION CAUGHT BY RENDERING LIBRARY ╞══"
    assert _should_log_stream_line(banner, state) is True
    assert _should_log_stream_line(banner, state) is False


def test_summarize_subprocess_output_keeps_assertions_drops_stack_frames() -> None:
    raw = "\n".join(
        [
            "══╡ EXCEPTION CAUGHT BY RENDERING LIBRARY ╞══",
            "The following assertion was thrown during performLayout():",
            "RenderFlex children have non-zero flex but incoming height constraints are unbounded.",
            "When the exception was thrown, this was the stack:",
            "#0      RenderFlex.performLayout (package:flutter/src/rendering/flex.dart:1324:9)",
            "#1      RenderObject.layout (package:flutter/src/rendering/object.dart:2907:7)",
            "  creator: Column ← Expanded ← Column",
            "The relevant error-causing widget was:",
            "  Column:file:///demo/lib/generated/login_layout.dart:24:297",
        ]
    )
    summary = summarize_subprocess_output(raw)
    assert "RenderFlex children have non-zero flex" in summary
    assert "login_layout.dart:24:297" in summary
    assert "RenderProxyBoxMixin.performLayout" not in summary
    assert "creator: Column" not in summary
    assert "When the exception was thrown" not in summary

