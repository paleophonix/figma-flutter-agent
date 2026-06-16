"""Snapshot stage for incremental sync metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.generator.ir.version import EMITTER_VERSION
from figma_flutter_agent.errors import SnapshotConflictError
from figma_flutter_agent.sync import (
    GenerationSnapshot,
    hash_file_contents,
    load_snapshot,
    save_snapshot,
)


@dataclass
class SnapshotStageRequest:
    """Inputs required to persist a generation snapshot."""

    project_dir: Path
    file_key: str
    node_id: str
    feature_name: str
    tree_hash: str
    colors_hash: str
    typography_hash: str
    spacing_hash: str
    planned_files: dict[str, str]
    layout_region_hash: str = ""
    cluster_hashes: dict[str, str] | None = None
    reference_image_hash: str | None = None
    expected_snapshot_version: int | None = None


def persist_generation_snapshot(request: SnapshotStageRequest) -> GenerationSnapshot:
    """Persist incremental sync metadata for a pipeline run.

    Args:
        request: Hashes and planned file contents for snapshot storage.

    Returns:
        Snapshot model written to disk.
    """
    expected_version = request.expected_snapshot_version

    def _build_snapshot(*, version: int) -> GenerationSnapshot:
        return GenerationSnapshot(
            file_key=request.file_key,
            node_id=request.node_id,
            feature_name=request.feature_name,
            tree_hash=request.tree_hash,
            colors_hash=request.colors_hash,
            typography_hash=request.typography_hash,
            spacing_hash=request.spacing_hash,
            file_hashes={
                path: hash_file_contents(content) for path, content in request.planned_files.items()
            },
            layout_region_hash=request.layout_region_hash,
            cluster_hashes=dict(request.cluster_hashes or {}),
            reference_image_hash=request.reference_image_hash,
            emitter_version=EMITTER_VERSION,
            version=version,
        )

    base_version = expected_version or 0
    snapshot = _build_snapshot(version=base_version + 1)
    try:
        save_snapshot(
            request.project_dir,
            request.feature_name,
            snapshot,
            expected_version=expected_version,
        )
        return snapshot
    except SnapshotConflictError:
        if expected_version is None:
            raise
        current = load_snapshot(request.project_dir, request.feature_name).snapshot
        if current is None:
            raise
        logger.warning(
            "Snapshot version conflict (expected {}, found {}); "
            "retrying persist once after parallel generate",
            expected_version,
            current.version,
        )
        snapshot = _build_snapshot(version=current.version + 1)
        save_snapshot(
            request.project_dir,
            request.feature_name,
            snapshot,
            expected_version=current.version,
        )
        return snapshot
