"""Tests for unified diff repair application."""

from __future__ import annotations

from figma_flutter_agent.llm.unified_diff import apply_unified_diff, is_unified_diff_text


def test_is_unified_diff_text_detects_hunk_header() -> None:
    diff = "@@ -2,1 +2,2 @@\n line\n-old\n+new\n line\n"
    assert is_unified_diff_text(diff)


def test_apply_unified_diff_replaces_line() -> None:
    base = "line one\nline two\nline three\n"
    diff = "@@ -1,3 +1,3 @@\n line one\n-line two\n+line TWO\n line three\n"
    patched = apply_unified_diff(base, diff)
    assert patched is not None
    assert "line TWO" in patched
    assert "line two" not in patched


def test_apply_unified_diff_rejects_mismatched_context() -> None:
    base = "line one\nline two\n"
    diff = "@@ -1,2 +1,2 @@\n line one\n-WRONG\n+line TWO\n"
    assert apply_unified_diff(base, diff) is None
