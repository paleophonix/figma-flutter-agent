"""Tests for canonical capture screen test helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.capture_screen_test import (
    refresh_capture_tests_in_planned,
    repair_capture_screen_test_imports,
)
from figma_flutter_agent.generator.renderer import DartRenderer


def test_repair_capture_screen_test_imports_adds_dart_ui() -> None:
    broken = """import 'dart:io';
import 'package:flutter/material.dart';

void main() {
  final x = ImageByteFormat.png;
}
"""
    fixed = repair_capture_screen_test_imports(broken)
    assert "import 'dart:ui' show ImageByteFormat;" in fixed
    assert "ImageByteFormat.png" in fixed


def test_repair_capture_screen_test_imports_fixes_painting_only_stub() -> None:
    """``painting.dart`` does not export ``ImageByteFormat`` — repair must add ``dart:ui``."""
    broken = """import 'package:flutter/painting.dart';

void main() {
  final x = ImageByteFormat.png;
}
"""
    fixed = repair_capture_screen_test_imports(broken)
    assert "import 'dart:ui' show ImageByteFormat;" in fixed


def test_refresh_capture_tests_replaces_broken_capture_file() -> None:
    planned = DartRenderer().render_capture_test(
        feature_name="welcome",
        screen_class="WelcomeScreen",
        package_name="demo_app",
        surface_width=414,
        surface_height=896,
        max_web_width=1200,
        collect_figma_keys=False,
    )
    path = "test/capture/welcome_screen_capture_test.dart"
    planned[path] = planned[path].replace("import 'dart:ui' show ImageByteFormat;\n", "")

    refreshed = refresh_capture_tests_in_planned(planned, package_name="demo_app")

    assert "import 'dart:ui' show ImageByteFormat;" in refreshed[path]
    assert "ImageByteFormat.png" in refreshed[path]


def test_capture_test_uses_bounded_pumps_before_png_encode() -> None:
    content = DartRenderer().render_capture_test(
        feature_name="welcome",
        screen_class="WelcomeScreen",
        package_name="demo_app",
        surface_width=414,
        surface_height=896,
        max_web_width=1200,
        collect_figma_keys=False,
    )["test/capture/welcome_screen_capture_test.dart"]
    assert "pumpAndSettle" not in content
    assert "Duration(milliseconds: 400)" in content
    assert "Duration(milliseconds: 500)" in content
    assert "toImage" in content
    last_pump_idx = content.rindex("await tester.pump(")
    image_idx = content.index("toImage")
    assert last_pump_idx < image_idx


def _run_async_body(content: str) -> str:
    """Return source inside the single ``tester.runAsync(() async { ... })`` block.

    Args:
        content: Rendered Dart capture test source.

    Returns:
        The brace-balanced body between the ``runAsync`` closure braces.

    Raises:
        AssertionError: When the ``runAsync`` block is missing or unbalanced.
    """
    marker = "tester.runAsync(() async {"
    start = content.index(marker)
    brace_start = content.index("{", start)
    depth = 0
    for i in range(brace_start, len(content)):
        char = content[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[brace_start + 1 : i]
    raise AssertionError("unbalanced runAsync block")


def _render_capture(*, collect_figma_keys: bool) -> str:
    return DartRenderer().render_capture_test(
        feature_name="welcome",
        screen_class="WelcomeScreen",
        package_name="demo_app",
        surface_width=414,
        surface_height=896,
        max_web_width=1200,
        collect_figma_keys=collect_figma_keys,
    )["test/capture/welcome_screen_capture_test.dart"]


def test_capture_test_png_readback_runs_in_real_async_zone() -> None:
    content = _render_capture(collect_figma_keys=False)
    body = _run_async_body(content)
    # Law capture_io_runs_in_real_async: encode AND file write live inside runAsync.
    assert "toImage" in body
    assert "toByteData" in body
    assert "writeAsBytes" in body
    # No real async (dart:io File) escapes the fake-async test zone.
    assert "await File(" not in content.replace(body, "")
    # Pumps stay in the fake zone, before the real-async block.
    last_pump_idx = content.rindex("await tester.pump(")
    assert last_pump_idx < content.index("tester.runAsync")
    assert "pumpAndSettle" not in content


def test_capture_test_keys_write_runs_in_real_async_zone() -> None:
    content = _render_capture(collect_figma_keys=True)
    body = _run_async_body(content)
    # Both the PNG write and the figma-keys write must be inside runAsync.
    assert "writeAsBytes" in body
    assert "collectFigmaKeyBounds" in body
    assert "writeAsString" in body
    outside = content.replace(body, "")
    assert "await File(" not in outside
    assert "writeAsString" not in outside
