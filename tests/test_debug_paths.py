"""Tests for .debug path helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.batch.manifest import ScreenEntry
from figma_flutter_agent.batch.run import _resolve_dump
from figma_flutter_agent.debug.paths import (
    agent_debug_root,
    capture_sandbox_dir,
    debug_capture_artifact_path,
    debug_path_display,
    emitter_reference_bundle_path,
    full_file_dump_path,
    layout_debug_filename,
    legacy_project_screen_root,
    legacy_raw_dump_path,
    processed_dump_path,
    project_wizard_prefs_path,
    pubspec_resolve_stamp_path,
    raw_dump_path,
    resolve_screen_ir_dump_file,
    resolve_screen_raw_dump,
    screen_debug_safe_project,
    screen_ir_dump_path,
    screen_root,
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
    assert debug_capture_artifact_path(project, feature, "capture") == (
        agent_debug_root() / "screen" / screen_debug_safe_project(project) / feature / "capture.png"
    )


def test_layout_debug_filename() -> None:
    assert layout_debug_filename("sign_in") == "sign_in_layout.json"


def test_raw_and_processed_paths(agent_root: Path) -> None:
    project = Path("/proj")
    feature = "home"
    root = screen_root(project, feature)
    assert raw_dump_path(project, feature) == root / "raw.json"
    assert processed_dump_path(project, feature) == root / "processed.json"
    assert screen_ir_dump_path(project, feature, "pre_emit") == root / "pre_emit.json"
    assert screen_ir_dump_path(project, feature, "llm_validated") == root / "llm_validated.json"
    assert emitter_reference_bundle_path(project, feature) == root / "emitter_ref.dart"
    assert sync_snapshot_path(project, feature) == root / "snapshot.json"
    assert full_file_dump_path(project, "abc123") == (
        agent_debug_root()
        / "screen"
        / screen_debug_safe_project(project)
        / "shared"
        / "full_file_abc123.json"
    )
    assert capture_sandbox_dir(project).resolve() == (project / ".sandbox").resolve()
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


def test_debug_path_display_prefers_project_then_agent(agent_root: Path) -> None:
    project = Path("/proj")
    in_project = project / "lib" / "main.dart"
    in_agent = screen_root(project, "feedback") / "llm_validated.json"
    assert debug_path_display(in_project, project) == "lib/main.dart"
    assert debug_path_display(in_agent, project) == (
        f".debug/screen/{screen_debug_safe_project(project)}/feedback/llm_validated.json"
    )


def test_debug_path_display_absolute_outside_roots(agent_root: Path) -> None:
    orphan = Path("/elsewhere/artifact.json")
    assert debug_path_display(orphan, Path("/proj")) == orphan.resolve().as_posix()


def test_resolve_screen_raw_dump_ignores_stale_manifest_path(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "apps" / "ataev"
    project.mkdir(parents=True)
    screen = ScreenEntry(
        feature="chats",
        node_id="281:14252",
        dump=project / ".figma_debug" / "raw" / "chats_layout.json",
    )
    short_root = agent_debug_root() / project.name / "chats"
    short_root.mkdir(parents=True)
    (short_root / "raw.json").write_text("{}", encoding="utf-8")

    resolved = _resolve_dump(screen, project)

    assert resolved == short_root / "raw.json"


def test_screen_debug_safe_project_uses_folder_name() -> None:
    assert screen_debug_safe_project(Path("apps/limbo")) == "limbo"
    assert screen_debug_safe_project(Path("/workspace/demo_app")) == "demo_app"


def test_resolve_screen_ir_dump_file_unique_agent_fallback(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "apps" / "limbo"
    project.mkdir(parents=True)
    ir_path = agent_debug_root() / "ataev" / "food_details" / "llm_validated.json"
    ir_path.parent.mkdir(parents=True)
    ir_path.write_text('{"screenIr": {"root": {"figmaId": "1"}}}', encoding="utf-8")

    resolved = resolve_screen_ir_dump_file(project, "food_details", "llm_validated")

    assert resolved == ir_path


def test_resolve_screen_raw_dump_uses_unique_agent_feature_dump(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "apps" / "limbo"
    project.mkdir(parents=True)
    only_dump = agent_debug_root() / "ataev" / "food_details" / "raw.json"
    only_dump.parent.mkdir(parents=True)
    only_dump.write_text("{}", encoding="utf-8")

    resolved = resolve_screen_raw_dump(project, "food_details", "1:1")

    assert resolved == only_dump


def test_agent_debug_root_isolated_from_checkout(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    """Pytest must not write screen artifacts into the real repo ``.debug/`` tree."""
    from figma_flutter_agent.config import agent_repo_root

    assert debug_agent_root == tmp_path
    assert agent_debug_root() == tmp_path / ".debug"
    assert agent_debug_root().resolve() != (agent_repo_root() / ".debug").resolve()
