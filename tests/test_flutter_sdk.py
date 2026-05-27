"""Tests for Flutter SDK resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from figma_flutter_agent.dev import flutter_sdk
from figma_flutter_agent.dev.flutter_sdk import (
    require_flutter_executable,
    resolve_dart_executable,
    resolve_flutter_executable,
)


@pytest.fixture(autouse=True)
def _reset_path_refresh() -> None:
    flutter_sdk._PATH_REFRESHED = False


def test_resolve_flutter_executable_from_sdk_root(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    flutter_name = "flutter.bat" if sys.platform == "win32" else "flutter"
    flutter_bin = bin_dir / flutter_name
    flutter_bin.write_text("", encoding="utf-8")

    resolved = resolve_flutter_executable(sdk_root=tmp_path)
    assert resolved == str(flutter_bin)


def test_resolve_flutter_executable_from_env(tmp_path: Path, monkeypatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    flutter_name = "flutter.bat" if sys.platform == "win32" else "flutter"
    flutter_bin = bin_dir / flutter_name
    flutter_bin.write_text("", encoding="utf-8")
    monkeypatch.setenv("FIGMA_FLUTTER_SDK", str(tmp_path))

    assert resolve_flutter_executable() == str(flutter_bin)


def test_resolve_dart_executable_next_to_flutter(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    flutter_name = "flutter.bat" if sys.platform == "win32" else "flutter"
    dart_name = "dart.bat" if sys.platform == "win32" else "dart"
    (bin_dir / flutter_name).write_text("", encoding="utf-8")
    dart_bin = bin_dir / dart_name
    dart_bin.write_text("", encoding="utf-8")

    assert resolve_dart_executable(sdk_root=tmp_path) == str(dart_bin)


def test_require_flutter_executable_raises_with_hint(monkeypatch) -> None:
    monkeypatch.setattr(flutter_sdk, "_PATH_REFRESHED", True)
    monkeypatch.setattr(flutter_sdk.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="FIGMA_FLUTTER_SDK"):
        require_flutter_executable(sdk_root="/nonexistent/flutter")
