"""Tests for offline fixture planned file builder."""

from __future__ import annotations

from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files
from figma_flutter_agent.validation.golden_capture import golden_test_relative_path


def test_build_fixture_planned_includes_layout_screen_and_golden_test() -> None:
    planned = build_fixture_planned_files("music_v2")
    planned = reconcile_planned_dart_files(planned)
    assert "lib/generated/music_v2_layout.dart" in planned
    assert "lib/features/music_v2/music_v2_screen.dart" in planned
    golden_rel = golden_test_relative_path("music_v2")
    assert golden_rel in planned
    assert "ValueKey('figma-" in planned["lib/generated/music_v2_layout.dart"]


def test_stack_positioned_input_has_bounded_width() -> None:
    planned = build_fixture_planned_files("sign_up_and_sign_in")
    layout = planned["lib/generated/sign_up_and_sign_in_layout.dart"]
    assert "figma-email-field" in layout
    email_idx = layout.index("figma-email-field")
    positioned = layout[email_idx - 120 : email_idx + 80]
    assert "width:" in positioned


def test_fixture_planned_theme_covers_layout_token_refs() -> None:
    planned = build_fixture_planned_files("reminders")
    assert "color2" in planned["lib/theme/app_colors.dart"]
    assert "static const double md" in planned["lib/theme/app_elevation.dart"]
    assert "static const double lg" in planned["lib/theme/app_spacing.dart"]
