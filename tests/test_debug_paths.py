"""Tests for .debug path helpers."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.paths import (
    capture_sandbox_dir,
    debug_capture_artifact_path,
    emitter_reference_bundle_path,
    full_file_dump_path,
    layout_debug_filename,
    legacy_raw_dump_path,
    processed_dump_path,
    project_wizard_prefs_path,
    pubspec_resolve_stamp_path,
    raw_dump_path,
    resolve_screen_raw_dump,
    screen_ir_dump_path,
    sync_snapshot_path,
)


def test_debug_capture_screen_artifact_paths() -> None:
    project = Path("/proj")
    feature = "login_version_1"
    assert debug_capture_artifact_path(project, feature, "flutter_render") == Path(
        "/proj/.debug/login_version_1/flutter_render.png"
    )


def test_layout_debug_filename() -> None:
    assert layout_debug_filename("sign_in") == "sign_in_layout.json"


def test_raw_and_processed_paths() -> None:
    project = Path("/proj")
    feature = "home"
    root = Path("/proj/.debug/home")
    assert raw_dump_path(project, feature) == root / "raw.json"
    assert processed_dump_path(project, feature) == root / "processed.json"
    assert screen_ir_dump_path(project, feature, "pre_emit") == root / "pre_emit.json"
    assert screen_ir_dump_path(project, feature, "llm_validated") == root / "llm_validated.json"
    assert emitter_reference_bundle_path(project, feature) == root / "emitter_ref.dart"
    assert sync_snapshot_path(project, feature) == root / "snapshot.json"
    assert full_file_dump_path(project, "abc123") == Path(
        "/proj/.figma-flutter/shared/full_file_abc123.json"
    )
    assert capture_sandbox_dir(project) == Path("/proj/.figma-flutter/capture-sandbox")
    assert project_wizard_prefs_path(project) == Path("/proj/wizard-state.yml")
    assert pubspec_resolve_stamp_path(project) == Path("/proj/pubspec_resolve.sha256")


def test_resolve_screen_raw_dump_prefers_canonical(tmp_path: Path) -> None:
    canonical = raw_dump_path(tmp_path, "sign_in")
    legacy = legacy_raw_dump_path(tmp_path, "1:3570")
    canonical.parent.mkdir(parents=True)
    canonical.write_text("{}", encoding="utf-8")
    legacy.write_text("{}", encoding="utf-8")

    resolved = resolve_screen_raw_dump(tmp_path, "sign_in", "1:3570")
    assert resolved == canonical


def test_resolve_screen_raw_dump_falls_back_to_legacy(tmp_path: Path) -> None:
    legacy = legacy_raw_dump_path(tmp_path, "1:3570")
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{}", encoding="utf-8")

    resolved = resolve_screen_raw_dump(tmp_path, "sign_in", "1:3570")
    assert resolved == legacy
