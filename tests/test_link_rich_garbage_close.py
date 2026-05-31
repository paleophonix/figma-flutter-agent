"""Repair surplus ``)`` before ``]`` after link ``Text.rich`` in button stacks."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from figma_flutter_agent.generator.dart_syntax_repairs import fix_garbage_closers_after_link_rich


def test_fix_garbage_closers_after_link_rich() -> None:
    broken = (
        "Text.rich(TextSpan(children: [TextSpan(text: 'LOG IN')]), "
        "textScaler: textScaler, textAlign: TextAlign.left))), "
        ")))])))), Positioned(left: 58.0"
    )
    fixed = fix_garbage_closers_after_link_rich(broken)
    assert ")))]))))," not in fixed
    assert ")))]))))," not in fixed
    assert "textAlign: TextAlign.left), Positioned" in fixed


def test_repair_dart_delimiters_fixes_link_row_for_dart_format() -> None:
    broken = (
        "import 'package:flutter/material.dart';\n"
        "void main() {\n"
        "  return Stack(children: ["
        "Text.rich(TextSpan(children: [TextSpan(text: 'a')]), textAlign: TextAlign.left))), "
        ")))])))), Positioned(left: 58.0, child: Text('x'))"
        "]); }\n"
    )
    repaired = fix_garbage_closers_after_link_rich(broken)
    td = Path(tempfile.mkdtemp()) / "t.dart"
    td.write_text(repaired, encoding="utf-8")
    import shutil

    dart = shutil.which("dart") or r"F:\src\flutter\bin\dart.bat"
    if not Path(dart).is_file():
        import pytest

        pytest.skip("dart SDK not available")
    result = subprocess.run(
        [dart, "format", str(td)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
