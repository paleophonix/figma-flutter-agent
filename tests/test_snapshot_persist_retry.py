"""Retry snapshot persist once after a parallel writer bumps the version."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.stages.snapshot import SnapshotStageRequest, persist_generation_snapshot
from figma_flutter_agent.sync.snapshot import GenerationSnapshot, load_snapshot, save_snapshot


def _base_request(project_dir: Path, *, expected: int | None) -> SnapshotStageRequest:
    return SnapshotStageRequest(
        project_dir=project_dir,
        file_key="abc",
        node_id="1:1",
        feature_name="music_v2",
        tree_hash="tree",
        colors_hash="c",
        typography_hash="t",
        spacing_hash="s",
        planned_files={"lib/a.dart": "class A {}"},
        expected_snapshot_version=expected,
    )


def test_persist_retries_after_parallel_version_bump(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    save_snapshot(
        project_dir,
        GenerationSnapshot(
            file_key="abc",
            node_id="1:1",
            feature_name="other",
            tree_hash="old",
            colors_hash="c",
            typography_hash="t",
            spacing_hash="s",
            version=176,
        ),
    )
    written = persist_generation_snapshot(_base_request(project_dir, expected=175))
    assert written.version == 177
    loaded = load_snapshot(project_dir).snapshot
    assert loaded is not None
    assert loaded.version == 177
    assert loaded.feature_name == "music_v2"
