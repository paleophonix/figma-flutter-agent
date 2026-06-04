"""Structural checks for the hand-authored sign_up cursor golden layout."""

from __future__ import annotations

from pathlib import Path

import pytest

_AGENT_ROOT = Path(__file__).resolve().parents[1]
_GOLDEN = (
    _AGENT_ROOT.parent
    / "flutter-demo-project"
    / "demo_app"
    / ".cursor_dart"
    / "sign_up_layout.dart"
)
_SCREEN = (
    _AGENT_ROOT.parent
    / "flutter-demo-project"
    / "demo_app"
    / ".cursor_dart"
    / "sign_up_screen.dart"
)


@pytest.mark.skipif(not _GOLDEN.is_file(), reason="demo_app cursor golden not present")
def test_sign_up_cursor_golden_wallpaper_and_interaction_contract() -> None:
    layout = _GOLDEN.read_text(encoding="utf-8")
    screen = _SCREEN.read_text(encoding="utf-8") if _SCREEN.is_file() else ""
    assert "class SignUpLayout extends StatelessWidget" in layout
    assert "class SignUpWallpaper" not in layout
    assert "group_6800_1_3610.svg" not in layout
    assert "vector_1_3609.svg" not in layout
    assert "SignUpWallpaper" not in screen
    assert "AppTypography.figmaFamily" in layout
    assert "width: 273.0" in layout
    assert "_onPurpleButtonText" in layout
    assert "top: 566.5" in layout
    assert "figma-1_3641" in layout
    assert "iconInsetRight" in layout
    assert "ColoredBox(color: AppColors.color3)" in layout
    assert "ColoredBox(color: AppColors.color1)" not in layout
    assert "Clip.hardEdge" in layout
    assert "_policyAccepted = false" in layout
    assert "top: 19.5" in layout
    assert "figma-1_3647" in layout
    assert "Transform.rotate(angle: -3.14" not in layout
    assert "'Name'" in layout and "_inputDecoration" in layout
    assert "'Email address'" in layout
    assert "'Password'" in layout
