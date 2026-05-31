"""Tests for canonical capture screen test helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.capture_screen_test import (
    refresh_capture_tests_in_planned,
    repair_capture_screen_test_imports,
)
from figma_flutter_agent.generator.renderer import DartRenderer


def test_repair_capture_screen_test_imports_adds_painting() -> None:
    broken = """import 'dart:io';
import 'package:flutter/material.dart';

void main() {
  final x = ImageByteFormat.png;
}
"""
    fixed = repair_capture_screen_test_imports(broken)
    assert "package:flutter/painting.dart" in fixed
    assert "ImageByteFormat.png" in fixed


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
    planned[path] = planned[path].replace("import 'package:flutter/painting.dart';\n", "")

    refreshed = refresh_capture_tests_in_planned(planned, package_name="demo_app")

    assert "package:flutter/painting.dart" in refreshed[path]
    assert "ImageByteFormat.png" in refreshed[path]
