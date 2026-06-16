"""Feedback bundle zip tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from control_panel.feedback.bundle import collect_screen_and_asset_files


@pytest.mark.control_plane
def test_collect_screen_and_asset_files(tmp_path: Path) -> None:
    lib = tmp_path / "lib" / "features" / "bank_home"
    lib.mkdir(parents=True)
    screen = lib / "bank_home_screen.dart"
    screen.write_text("void main() {}", encoding="utf-8")
    assets = tmp_path / "assets" / "icons"
    assets.mkdir(parents=True)
    icon = assets / "logo.png"
    icon.write_bytes(b"png")
    files = collect_screen_and_asset_files(project_dir=tmp_path, feature_slug="bank_home")
    assert any("bank_home_screen.dart" in key for key in files)
    assert any(key.startswith("assets/") for key in files)
