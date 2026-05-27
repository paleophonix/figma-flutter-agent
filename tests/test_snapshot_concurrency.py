"""Tests for optimistic snapshot versioning and atomic persistence."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from figma_flutter_agent.errors import SnapshotConflictError
from figma_flutter_agent.sync.snapshot import (
    GenerationSnapshot,
    load_snapshot,
    save_snapshot,
    snapshot_path,
)


def _snapshot(*, version: int = 1, tree_hash: str = "tree") -> GenerationSnapshot:
    return GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="demo",
        tree_hash=tree_hash,
        colors_hash="colors",
        typography_hash="typography",
        spacing_hash="spacing",
        version=version,
    )


def test_save_snapshot_raises_on_version_conflict(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    save_snapshot(project_dir, _snapshot(version=1))

    with pytest.raises(SnapshotConflictError, match="version conflict"):
        save_snapshot(project_dir, _snapshot(version=2), expected_version=0)


def test_save_snapshot_atomic_write_leaves_no_tmp_files(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    save_snapshot(project_dir, _snapshot(version=1))

    snap_dir = project_dir / ".figma-flutter"
    assert snapshot_path(project_dir).is_file()
    assert list(snap_dir.glob("*.tmp")) == []


def test_save_snapshot_retry_after_conflict_succeeds(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    save_snapshot(project_dir, _snapshot(version=1, tree_hash="v1"))

    with pytest.raises(SnapshotConflictError):
        save_snapshot(project_dir, _snapshot(version=99, tree_hash="stale"), expected_version=0)

    save_snapshot(project_dir, _snapshot(version=2, tree_hash="v2"), expected_version=1)
    loaded = load_snapshot(project_dir).snapshot
    assert loaded is not None
    assert loaded.version == 2
    assert loaded.tree_hash == "v2"


def test_parallel_save_snapshot_one_writer_wins(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    save_snapshot(project_dir, _snapshot(version=1))

    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def _writer(label: str, tree_hash: str) -> None:
        try:
            barrier.wait(timeout=5)
            save_snapshot(
                project_dir,
                _snapshot(version=2, tree_hash=tree_hash),
                expected_version=1,
            )
            outcomes.append(f"{label}:ok")
        except SnapshotConflictError:
            outcomes.append(f"{label}:conflict")
        except threading.BrokenBarrierError as exc:
            outcomes.append(f"{label}:barrier:{exc}")

    threads = [
        threading.Thread(target=_writer, args=("a", "hash-a")),
        threading.Thread(target=_writer, args=("b", "hash-b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(outcomes) == 2
    assert outcomes.count("a:ok") + outcomes.count("b:ok") == 1
    assert outcomes.count("a:conflict") + outcomes.count("b:conflict") == 1

    payload = json.loads(snapshot_path(project_dir).read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert payload["tree_hash"] in {"hash-a", "hash-b"}
