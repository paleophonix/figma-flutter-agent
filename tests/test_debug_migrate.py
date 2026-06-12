"""Tests for legacy ``.figma-flutter`` → ``.debug`` artifact migration."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.migrate import (
    ensure_project_debug_layout,
    migrate_capture_sandbox_nested_layout,
    migrate_legacy_project_artifacts,
)
from figma_flutter_agent.debug.paths import (
    capture_sandbox_dir,
    emitter_reference_bundle_path,
    figma_reference_png_path,
    project_wizard_prefs_path,
    sync_snapshot_path,
)


def test_migrate_legacy_figma_flutter_tree(tmp_path: Path) -> None:
    legacy = tmp_path / ".figma-flutter"
    (legacy / "reference").mkdir(parents=True)
    (legacy / "reference" / "login_figma.png").write_bytes(b"png")
    (legacy / "snapshot.json").write_text("{}", encoding="utf-8")
    (legacy / "wizard-state.yml").write_text("active_screen: login\n", encoding="utf-8")
    (legacy / "capture-sandbox").mkdir()
    (legacy / "capture-sandbox" / "pubspec.yaml").write_text("name: warm\n", encoding="utf-8")

    flat_emitter = tmp_path / ".debug" / "reference"
    flat_emitter.mkdir(parents=True)
    (flat_emitter / "home_screen.dart").write_text("// bundle\n", encoding="utf-8")

    moved = migrate_legacy_project_artifacts(tmp_path)
    assert moved >= 4
    assert figma_reference_png_path(tmp_path, "login").read_bytes() == b"png"
    assert sync_snapshot_path(tmp_path).is_file()
    assert project_wizard_prefs_path(tmp_path).is_file()
    assert capture_sandbox_dir(tmp_path).is_dir()
    assert emitter_reference_bundle_path(tmp_path, "home").is_file()
    assert not legacy.exists()


def test_migrate_project_debug_dir_rename(tmp_path: Path) -> None:
    legacy = tmp_path / ".figma_debug"
    legacy.mkdir()
    (legacy / "wizard-state.yml").write_text("x: 1\n", encoding="utf-8")

    from figma_flutter_agent.debug.migrate import migrate_project_debug_dir_rename

    assert migrate_project_debug_dir_rename(tmp_path) == 1
    assert (tmp_path / ".debug" / "wizard-state.yml").is_file()
    assert not legacy.exists()


def test_migrate_capture_sandbox_nested_layout(tmp_path: Path) -> None:
    legacy = tmp_path / ".debug" / "capture-sandbox"
    legacy.mkdir(parents=True)
    (legacy / "pubspec.yaml").write_text("name: warm\n", encoding="utf-8")

    assert migrate_capture_sandbox_nested_layout(tmp_path) == 1
    assert capture_sandbox_dir(tmp_path).is_dir()
    assert (capture_sandbox_dir(tmp_path) / "pubspec.yaml").is_file()
    assert not legacy.exists()


def test_ensure_project_debug_layout_is_idempotent(tmp_path: Path) -> None:
    legacy = tmp_path / ".figma-flutter" / "reference"
    legacy.mkdir(parents=True)
    (legacy / "screen_figma.png").write_bytes(b"1")

    ensure_project_debug_layout(tmp_path)
    ensure_project_debug_layout(tmp_path)

    assert figma_reference_png_path(tmp_path, "screen").read_bytes() == b"1"
