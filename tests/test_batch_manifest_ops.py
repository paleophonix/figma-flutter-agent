"""Tests for batch manifest merge and screen removal."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.batch.manifest import (
    BatchManifest,
    ScreenEntry,
    load_batch_manifest,
    merge_manifest_screens,
    remove_screens_from_manifest,
    rename_screen_in_manifest,
    write_batch_manifest,
)
from figma_flutter_agent.debug.paths import (
    dart_bundle_path,
    processed_dump_path,
    raw_dump_path,
)


def test_merge_manifest_screens_keeps_unrelated_entries(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    existing = BatchManifest(
        file_key="abc123",
        project_dir=project_dir,
        screens=(
            ScreenEntry(feature="sign_in", node_id="1:100"),
            ScreenEntry(feature="home", node_id="1:200"),
        ),
    )
    merged = merge_manifest_screens(
        existing,
        (
            ScreenEntry(feature="sign_in_v2", node_id="1:100"),
            ScreenEntry(feature="profile", node_id="1:300"),
        ),
    )
    assert [screen.feature for screen in merged.screens] == ["home", "sign_in_v2", "profile"]
    assert merged.file_key == "abc123"


def test_remove_screens_from_manifest_deletes_dumps(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    dump_path = project_dir / ".figma_debug" / "raw" / "sign_in_layout.json"
    dump_path.parent.mkdir(parents=True)
    dump_path.write_text("{}", encoding="utf-8")
    manifest_path = project_dir / "screens.yaml"
    write_batch_manifest(
        manifest_path,
        BatchManifest(
            file_key="abc123",
            project_dir=project_dir,
            screens=(
                ScreenEntry(feature="sign_in", node_id="1:100", dump=dump_path),
                ScreenEntry(feature="home", node_id="1:200"),
            ),
        ),
    )

    updated, removed = remove_screens_from_manifest(manifest_path, ["sign_in", "home"])

    assert removed == ("home", "sign_in")
    assert updated.screens == ()
    assert not dump_path.is_file()
    assert load_batch_manifest(manifest_path).screens == ()


def test_rename_screen_in_manifest_moves_debug_artifacts(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    old_dump = raw_dump_path(project_dir, "background")
    old_dump.parent.mkdir(parents=True)
    old_dump.write_text("{}", encoding="utf-8")
    processed = processed_dump_path(project_dir, "background")
    processed.parent.mkdir(parents=True, exist_ok=True)
    processed.write_text("{}", encoding="utf-8")
    dart_bundle = dart_bundle_path(project_dir, "background")
    dart_bundle.parent.mkdir(parents=True, exist_ok=True)
    dart_bundle.write_text("// screen", encoding="utf-8")
    manifest_path = project_dir / "screens.yaml"
    write_batch_manifest(
        manifest_path,
        BatchManifest(
            file_key="abc123",
            project_dir=project_dir,
            screens=(ScreenEntry(feature="background", node_id="1:100", dump=old_dump),),
        ),
    )

    updated, previous, renamed = rename_screen_in_manifest(
        manifest_path,
        "background",
        "profile_data",
    )

    assert previous == "background"
    assert renamed == "profile_data"
    assert updated.screens[0].feature == "profile_data"
    assert raw_dump_path(project_dir, "profile_data").is_file()
    assert processed_dump_path(project_dir, "profile_data").is_file()
    assert dart_bundle_path(project_dir, "profile_data").is_file()
    assert not old_dump.is_file()
    reloaded = load_batch_manifest(manifest_path)
    assert reloaded.screens[0].dump == raw_dump_path(project_dir, "profile_data")


def test_rename_screen_in_manifest_rejects_duplicate_slug(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    manifest_path = project_dir / "screens.yaml"
    write_batch_manifest(
        manifest_path,
        BatchManifest(
            file_key="abc123",
            project_dir=project_dir,
            screens=(
                ScreenEntry(feature="sign_in", node_id="1:100"),
                ScreenEntry(feature="home", node_id="1:200"),
            ),
        ),
    )
    with pytest.raises(ValueError, match="already used"):
        rename_screen_in_manifest(manifest_path, "sign_in", "home")


def test_remove_screens_from_manifest_rejects_empty_names(tmp_path: Path) -> None:
    manifest_path = tmp_path / "screens.yaml"
    with pytest.raises(ValueError, match="At least one"):
        remove_screens_from_manifest(manifest_path, [])
