"""Unit tests for pipeline incremental sync helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.version import EMITTER_VERSION
from figma_flutter_agent.pipeline.incremental import (
    DesignHashState,
    should_skip_snapshot_persist,
)
from figma_flutter_agent.sync.snapshot import GenerationSnapshot, hash_file_contents


def test_should_skip_snapshot_persist_when_unchanged() -> None:
    planned = {"lib/main.dart": "content"}
    file_hash = hash_file_contents(planned["lib/main.dart"])
    previous = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="demo",
        tree_hash="tree",
        colors_hash="colors",
        typography_hash="typography",
        spacing_hash="spacing",
        file_hashes={"lib/main.dart": file_hash},
        emitter_version=EMITTER_VERSION,
        version=1,
    )
    hashes = DesignHashState(
        tree_hash="tree",
        colors_hash="colors",
        typography_hash="typography",
        spacing_hash="spacing",
    )

    assert should_skip_snapshot_persist(
        previous_snapshot=previous,
        files_to_write={},
        hashes=hashes,
        planned_files=planned,
    )


def test_should_not_skip_snapshot_persist_when_files_written() -> None:
    previous = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name="demo",
        tree_hash="tree",
        colors_hash="colors",
        typography_hash="typography",
        spacing_hash="spacing",
        file_hashes={},
        version=1,
    )
    hashes = DesignHashState(
        tree_hash="tree",
        colors_hash="colors",
        typography_hash="typography",
        spacing_hash="spacing",
    )

    assert not should_skip_snapshot_persist(
        previous_snapshot=previous,
        files_to_write={"lib/main.dart": "new"},
        hashes=hashes,
        planned_files={"lib/main.dart": "new"},
    )
