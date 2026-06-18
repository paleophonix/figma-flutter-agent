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


def test_capture_test_png_readback_runs_in_real_async_zone() -> None:
    content = DartRenderer().render_capture_test(
        feature_name="welcome",
        screen_class="WelcomeScreen",
        package_name="demo_app",
        surface_width=414,
        surface_height=896,
        max_web_width=1200,
        collect_figma_keys=False,
    )["test/capture/welcome_screen_capture_test.dart"]
    run_async_idx = content.index("tester.runAsync")
    to_image_idx = content.index("toImage")
    byte_data_idx = content.index("toByteData")
    assert run_async_idx < to_image_idx < byte_data_idx
    last_pump_idx = content.rindex("await tester.pump(")
    assert last_pump_idx < run_async_idx
    write_idx = content.index("writeAsBytes")
    assert byte_data_idx < write_idx
