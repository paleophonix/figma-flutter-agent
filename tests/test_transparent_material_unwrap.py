"""Unwrap redundant LLM ``Material(type: MaterialType.transparency)`` wrappers."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from figma_flutter_agent.generator.dart.syntax_repairs import (
    fix_garbage_closers_after_link_rich,
    unwrap_transparent_material_wrappers,
)
from figma_flutter_agent.generator.planned.reconcile import _sanitize_screen_dart_syntax


def test_unwrap_transparent_material_preserves_mouse_region() -> None:
    source = (
        "child: Material(\n"
        "                    type: MaterialType.transparency,\n"
        "                    child: MouseRegion(cursor: SystemMouseCursors.click, "
        "child: Text('SIGN UP')),\n"
        "                  ))),"
    )
    fixed = unwrap_transparent_material_wrappers(source)
    assert "MaterialType.transparency" not in fixed
    assert "MouseRegion(cursor:" in fixed
    assert fixed.count("Material(") == 0


def test_sanitize_demo_button_stack_closers() -> None:
    broken = (
        "Stack(children: ["
        "Positioned(child: Material(type: MaterialType.transparency, child: "
        "MouseRegion(child: GestureDetector(child: Text('SIGN UP', textAlign: TextAlign.left)))),"
        "))), "
        "Positioned(child: Semantics(child: Material(type: MaterialType.transparency, child: "
        "MouseRegion(child: GestureDetector(child: Text.rich(TextSpan(children: "
        "[TextSpan(text: 'LOG IN')]), textScaler: textScaler, textAlign: TextAlign.left))), "
        ")))])))), Positioned(left: 58.0, child: Text('next'))"
        "])"
    )
    fixed = _sanitize_screen_dart_syntax(broken)
    assert ")))]))))," not in fixed
    assert ")))]))))," not in fixed


def test_unwrap_then_dart_format() -> None:
    broken = (
        "import 'package:flutter/material.dart';\n"
        "void main() {\n"
        "  return Stack(children: ["
        "Material(type: MaterialType.transparency, child: "
        "Text.rich(TextSpan(children: [TextSpan(text: 'a')]), textAlign: TextAlign.left))), "
        ")))])))), Positioned(left: 1.0, child: Text('x'))"
        "]); }\n"
    )
    fixed = fix_garbage_closers_after_link_rich(unwrap_transparent_material_wrappers(broken))
    td = Path(tempfile.mkdtemp()) / "t.dart"
    td.write_text(fixed, encoding="utf-8")
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
