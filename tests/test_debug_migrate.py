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
    dart_debug_snapshot_path,
    emitter_reference_bundle_path,
    figma_reference_png_path,
    processed_dump_path,
    project_wizard_prefs_path,
    raw_dump_path,
    screen_ir_dump_path,
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
    from figma_flutter_agent.debug.migrate import ensure_project_debug_layout, migrate_screen_centric_layout

    migrate_screen_centric_layout(tmp_path)
    ensure_project_debug_layout(tmp_path)
    assert moved >= 4
    assert figma_reference_png_path(tmp_path, "login").read_bytes() == b"png"
    assert sync_snapshot_path(tmp_path, "login").is_file()
    assert project_wizard_prefs_path(tmp_path).is_file()
    assert capture_sandbox_dir(tmp_path).is_dir()
    assert emitter_reference_bundle_path(tmp_path, "home").is_file()
    assert not (legacy / "snapshot.json").exists()
    assert not (legacy / "wizard-state.yml").exists()


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


def test_migrate_screen_centric_layout_from_v2(tmp_path: Path) -> None:
    feature = "login"
    (tmp_path / ".debug" / "raw").mkdir(parents=True)
    (tmp_path / ".debug" / "processed").mkdir(parents=True)
    (tmp_path / ".debug" / "dart").mkdir(parents=True)
    (tmp_path / ".debug" / "ir").mkdir(parents=True)
    (tmp_path / ".debug" / "raw" / f"{feature}_layout.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".debug" / "processed" / f"{feature}_layout.json").write_text(
        "{}", encoding="utf-8"
    )
    (tmp_path / ".debug" / "dart" / f"{feature}_screen.dart").write_text("// dart\n", encoding="utf-8")
    (tmp_path / ".debug" / "ir" / f"{feature}_pre_emit.json").write_text("{}", encoding="utf-8")

    from figma_flutter_agent.debug.migrate import migrate_screen_centric_layout

    moved = migrate_screen_centric_layout(tmp_path)
    assert moved >= 4
    assert raw_dump_path(tmp_path, feature).is_file()
    assert processed_dump_path(tmp_path, feature).is_file()
    assert dart_debug_snapshot_path(tmp_path, feature, "final").is_file()
    assert screen_ir_dump_path(tmp_path, feature, "pre_emit").is_file()


def test_ensure_project_debug_layout_is_idempotent(tmp_path: Path) -> None:
    legacy = tmp_path / ".figma-flutter" / "reference"
    legacy.mkdir(parents=True)
    (legacy / "screen_figma.png").write_bytes(b"1")

    ensure_project_debug_layout(tmp_path)
    ensure_project_debug_layout(tmp_path)

    assert figma_reference_png_path(tmp_path, "screen").read_bytes() == b"1"
