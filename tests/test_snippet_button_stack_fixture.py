"""Fixture pair: broken button-stack closers → golden after sanitize."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from figma_flutter_agent.generator.dart.syntax_repairs import sanitize_emit_screen_syntax
from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

_FIXTURES = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "flutter_skeleton"
    / "test"
    / "fixtures"
)


def _main_return_body(source: str) -> str:
    start = source.index("return Stack")
    end = source.rindex(");") + 2
    body = source[start:end]
    if not body.endswith(";"):
        body = f"{body};"
    return body


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", "", text)


def test_broken_fixture_sanitizes_to_golden() -> None:
    broken = (_FIXTURES / "snippet_button_stack_broken.txt").read_text(encoding="utf-8")
    golden = (_FIXTURES / "snippet_button_stack.dart").read_text(encoding="utf-8")
    sanitized = sanitize_emit_screen_syntax(_main_return_body(broken))
    fixed = sanitized if sanitized.endswith(";") else f"{sanitized};"
    assert _collapse_ws(fixed) == _collapse_ws(_main_return_body(golden))
    assert ")))]})))))}," not in fixed
    assert ")))])))}," not in fixed


def test_golden_fixture_passes_delimiter_check() -> None:
    golden = (_FIXTURES / "snippet_button_stack.dart").read_text(encoding="utf-8")
    assert validate_dart_delimiters(golden) is None


def test_golden_fixture_dart_format() -> None:
    golden = (_FIXTURES / "snippet_button_stack.dart").read_text(encoding="utf-8")
    import shutil

    dart = shutil.which("dart") or r"F:\src\flutter\bin\dart.bat"
    if not Path(dart).is_file():
        pytest.skip("dart SDK not available")
    td = Path(tempfile.mkdtemp()) / "snippet_button_stack.dart"
    td.write_text(golden, encoding="utf-8")
    result = subprocess.run(
        [dart, "format", str(td)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_broken_fixture_dart_format_after_sanitize() -> None:
    broken = (_FIXTURES / "snippet_button_stack_broken.txt").read_text(encoding="utf-8")
    import shutil

    dart = shutil.which("dart") or r"F:\src\flutter\bin\dart.bat"
    if not Path(dart).is_file():
        pytest.skip("dart SDK not available")
    sanitized = sanitize_emit_screen_syntax(_main_return_body(broken))
    fixed_body = sanitized if sanitized.endswith(";") else f"{sanitized};"
    source = (
        "import 'package:flutter/material.dart';\n"
        "void main() {\n"
        "  final textScaler = TextScaler.noScaling;\n"
        f"  {fixed_body}\n"
        "}\n"
    )
    td = Path(tempfile.mkdtemp()) / "snippet_button_stack_sanitized.dart"
    td.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [dart, "format", str(td)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
