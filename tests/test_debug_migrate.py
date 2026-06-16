"""Tests for legacy ``.figma-flutter`` → ``.debug`` artifact migration."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.migrate import (
    ensure_project_debug_layout,
    migrate_capture_sandbox_nested_layout,
    migrate_capture_sandbox_to_agent_debug,
    migrate_project_scoped_screen_layout,
    migrate_screen_artifacts_to_agent_repo,
)
from figma_flutter_agent.debug.paths import (
    capture_sandbox_dir,
    dart_debug_snapshot_path,
    emitter_reference_bundle_path,
    figma_reference_png_path,
    legacy_flat_agent_screen_root,
    legacy_project_screen_root,
    processed_dump_path,
    project_wizard_prefs_path,
    raw_dump_path,
    screen_ir_dump_path,
    screen_root,
    sync_snapshot_path,
)


def test_migrate_legacy_figma_flutter_tree(debug_agent_root: Path, tmp_path: Path) -> None:
    project = tmp_path / "flutter"
    project.mkdir()
    legacy = project / ".figma-flutter"
    (legacy / "reference").mkdir(parents=True)
    (legacy / "reference" / "login_figma.png").write_bytes(b"png")
    (legacy / "snapshot.json").write_text("{}", encoding="utf-8")
    (legacy / "wizard-state.yml").write_text("active_screen: login\n", encoding="utf-8")
    (legacy / "capture-sandbox").mkdir()
    (legacy / "capture-sandbox" / "pubspec.yaml").write_text("name: warm\n", encoding="utf-8")

    flat_emitter = project / ".debug" / "reference"
    flat_emitter.mkdir(parents=True)
    (flat_emitter / "home_screen.dart").write_text("// bundle\n", encoding="utf-8")

    ensure_project_debug_layout(project)

    assert figma_reference_png_path(project, "login").read_bytes() == b"png"
    assert sync_snapshot_path(project, "login").is_file()
    assert project_wizard_prefs_path(project).is_file()
    assert capture_sandbox_dir(project).is_dir()
    assert emitter_reference_bundle_path(project, "home").is_file()
    assert not (legacy / "snapshot.json").exists()
    assert not (legacy / "wizard-state.yml").exists()
    assert not (project / ".debug").exists()


def test_migrate_project_debug_dir_rename(debug_agent_root: Path, tmp_path: Path) -> None:
    project = tmp_path / "flutter"
    project.mkdir()
    legacy = project / ".figma_debug"
    legacy.mkdir()
    (legacy / "wizard-state.yml").write_text("x: 1\n", encoding="utf-8")

    from figma_flutter_agent.debug.migrate import migrate_project_debug_dir_rename

    assert migrate_project_debug_dir_rename(project) == 1
    assert (project / ".debug" / "wizard-state.yml").is_file()
    assert not legacy.exists()


def test_migrate_capture_sandbox_nested_layout(debug_agent_root: Path, tmp_path: Path) -> None:
    project = tmp_path / "flutter"
    project.mkdir()
    legacy = project / ".debug" / "capture-sandbox"
    legacy.mkdir(parents=True)
    (legacy / "pubspec.yaml").write_text("name: warm\n", encoding="utf-8")

    assert migrate_capture_sandbox_nested_layout(project) == 1
    assert capture_sandbox_dir(project).is_dir()
    assert (capture_sandbox_dir(project) / "pubspec.yaml").is_file()
    assert not legacy.exists()


def test_migrate_capture_sandbox_to_agent_debug(debug_agent_root: Path, tmp_path: Path) -> None:
    project = tmp_path / "flutter"
    project.mkdir()
    legacy = project / ".figma-flutter" / "capture-sandbox"
    legacy.mkdir(parents=True)
    (legacy / "pubspec.yaml").write_text("name: warm\n", encoding="utf-8")

    assert migrate_capture_sandbox_to_agent_debug(project) == 1
    assert capture_sandbox_dir(project).is_dir()
    assert (capture_sandbox_dir(project) / "pubspec.yaml").is_file()
    assert not legacy.exists()


def test_migrate_screen_centric_layout_from_v2(debug_agent_root: Path, tmp_path: Path) -> None:
    project = tmp_path / "flutter"
    project.mkdir()
    feature = "login"
    (project / ".debug" / "raw").mkdir(parents=True)
    (project / ".debug" / "processed").mkdir(parents=True)
    (project / ".debug" / "dart").mkdir(parents=True)
    (project / ".debug" / "ir").mkdir(parents=True)
    (project / ".debug" / "raw" / f"{feature}_layout.json").write_text("{}", encoding="utf-8")
    (project / ".debug" / "processed" / f"{feature}_layout.json").write_text("{}", encoding="utf-8")
    (project / ".debug" / "dart" / f"{feature}_screen.dart").write_text(
        "// dart\n", encoding="utf-8"
    )
    (project / ".debug" / "ir" / f"{feature}_pre_emit.json").write_text("{}", encoding="utf-8")

    from figma_flutter_agent.debug.migrate import migrate_screen_centric_layout

    moved = migrate_screen_centric_layout(project)
    migrate_screen_artifacts_to_agent_repo(project)
    assert moved >= 4
    assert raw_dump_path(project, feature).is_file()
    assert processed_dump_path(project, feature).is_file()
    assert dart_debug_snapshot_path(project, feature, "final").is_file()
    assert screen_ir_dump_path(project, feature, "pre_emit").is_file()
    assert not (project / ".debug").exists()


def test_migrate_screen_artifacts_to_agent_repo_moves_feature_dirs(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "flutter"
    project.mkdir()
    feature_dir = legacy_project_screen_root(project, "feedback")
    feature_dir.mkdir(parents=True)
    (feature_dir / "raw.json").write_text("{}", encoding="utf-8")
    (feature_dir / "last.log").write_text("run\n", encoding="utf-8")

    moved = migrate_screen_artifacts_to_agent_repo(project)

    assert moved >= 2
    assert (legacy_flat_agent_screen_root("feedback") / "raw.json").is_file()
    assert (legacy_flat_agent_screen_root("feedback") / "last.log").is_file()
    assert not (project / ".debug").exists()


def test_migrate_project_scoped_screen_layout_moves_flat_feature_dirs(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "flutter"
    project.mkdir()
    feature = "feedback"
    flat_root = legacy_flat_agent_screen_root(feature)
    flat_root.mkdir(parents=True)
    (flat_root / "raw.json").write_text("{}", encoding="utf-8")
    (project / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: abc",
                "project_dir: .",
                "screens:",
                f"  - feature: {feature}",
                "    node_id: 1-1",
            ]
        ),
        encoding="utf-8",
    )

    moved = migrate_project_scoped_screen_layout(project)

    assert moved >= 1
    scoped = screen_root(project, feature)
    assert (scoped / "raw.json").is_file()
    assert not flat_root.exists()


def test_ensure_project_debug_layout_is_idempotent(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "flutter"
    project.mkdir()
    legacy = project / ".figma-flutter" / "reference"
    legacy.mkdir(parents=True)
    (legacy / "screen_figma.png").write_bytes(b"1")

    ensure_project_debug_layout(project)
    ensure_project_debug_layout(project)

    assert figma_reference_png_path(project, "screen").read_bytes() == b"1"
