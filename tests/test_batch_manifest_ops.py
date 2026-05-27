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
    write_batch_manifest,
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


def test_remove_screens_from_manifest_rejects_empty_names(tmp_path: Path) -> None:
    manifest_path = tmp_path / "screens.yaml"
    with pytest.raises(ValueError, match="At least one"):
        remove_screens_from_manifest(manifest_path, [])
