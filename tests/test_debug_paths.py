"""Tests for .debug path helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.debug.paths import (
    agent_debug_root,
    capture_sandbox_dir,
    debug_capture_artifact_path,
    emitter_reference_bundle_path,
    full_file_dump_path,
    layout_debug_filename,
    legacy_project_screen_root,
    legacy_raw_dump_path,
    processed_dump_path,
    project_wizard_prefs_path,
    pubspec_resolve_stamp_path,
    raw_dump_path,
    resolve_screen_raw_dump,
    screen_ir_dump_path,
    sync_snapshot_path,
)


@pytest.fixture
def agent_root(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(
        "figma_flutter_agent.debug.paths.agent_repo_root",
        lambda: Path("/agent"),
    )
    return Path("/agent")


def test_debug_capture_screen_artifact_paths(agent_root: Path) -> None:
    project = Path("/proj")
    feature = "login_version_1"
    assert debug_capture_artifact_path(project, feature, "flutter_render") == Path(
        "/agent/.debug/login_version_1/flutter_render.png"
    )


def test_layout_debug_filename() -> None:
    assert layout_debug_filename("sign_in") == "sign_in_layout.json"


def test_raw_and_processed_paths(agent_root: Path) -> None:
    project = Path("/proj")
    feature = "home"
    root = agent_debug_root() / "home"
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


def test_resolve_screen_raw_dump_prefers_canonical(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    canonical = raw_dump_path(project, "sign_in")
    legacy = legacy_raw_dump_path(project, "1:3570")
    canonical.parent.mkdir(parents=True)
    canonical.write_text("{}", encoding="utf-8")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("{}", encoding="utf-8")

    resolved = resolve_screen_raw_dump(project, "sign_in", "1:3570")
    assert resolved == canonical


def test_resolve_screen_raw_dump_falls_back_to_project_layout(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    legacy_project = legacy_project_screen_root(project, "sign_in") / "raw.json"
    legacy_project.parent.mkdir(parents=True)
    legacy_project.write_text("{}", encoding="utf-8")

    resolved = resolve_screen_raw_dump(project, "sign_in", "1:3570")
    assert resolved == legacy_project


def test_resolve_screen_raw_dump_falls_back_to_legacy_node_dump(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    legacy = legacy_raw_dump_path(project, "1:3570")
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{}", encoding="utf-8")

    resolved = resolve_screen_raw_dump(project, "sign_in", "1:3570")
    assert resolved == legacy
