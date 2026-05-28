"""Incremental sync snapshot persistence."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import FlutterProjectError, SnapshotConflictError
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
)

SNAPSHOT_DIR_NAME = ".figma-flutter"
SNAPSHOT_FILE_NAME = "snapshot.json"
SNAPSHOT_VERSION = 1


def _coerce_file_hashes(value: object) -> dict[str, str]:
    """Coerce persisted file hash map from JSON payload."""
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _coerce_version(value: object) -> int:
    """Coerce snapshot version from JSON payload."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return SNAPSHOT_VERSION


@dataclass
class GenerationSnapshot:
    """Persisted generation state for incremental sync."""

    file_key: str
    node_id: str
    feature_name: str
    tree_hash: str
    colors_hash: str
    typography_hash: str
    spacing_hash: str
    file_hashes: dict[str, str] = field(default_factory=dict)
    layout_region_hash: str = ""
    cluster_hashes: dict[str, str] = field(default_factory=dict)
    reference_image_hash: str | None = None
    version: int = SNAPSHOT_VERSION
    updated_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

    def to_dict(self) -> dict[str, object]:
        """Return an explicit JSON-serializable snapshot payload."""
        return {
            "file_key": self.file_key,
            "node_id": self.node_id,
            "feature_name": self.feature_name,
            "tree_hash": self.tree_hash,
            "colors_hash": self.colors_hash,
            "typography_hash": self.typography_hash,
            "spacing_hash": self.spacing_hash,
            "file_hashes": dict(self.file_hashes),
            "layout_region_hash": self.layout_region_hash,
            "cluster_hashes": dict(self.cluster_hashes),
            "reference_image_hash": self.reference_image_hash,
            "version": self.version,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> GenerationSnapshot:
        """Build a snapshot from persisted JSON payload."""
        return cls(
            file_key=str(payload["file_key"]),
            node_id=str(payload["node_id"]),
            feature_name=str(payload["feature_name"]),
            tree_hash=str(payload["tree_hash"]),
            colors_hash=str(payload["colors_hash"]),
            typography_hash=str(payload["typography_hash"]),
            spacing_hash=str(payload["spacing_hash"]),
            file_hashes=_coerce_file_hashes(payload.get("file_hashes")),
            layout_region_hash=str(payload.get("layout_region_hash") or ""),
            cluster_hashes=_coerce_file_hashes(payload.get("cluster_hashes")),
            reference_image_hash=(
                str(payload["reference_image_hash"])
                if payload.get("reference_image_hash") is not None
                else None
            ),
            version=_coerce_version(payload.get("version", SNAPSHOT_VERSION)),
            updated_at=str(payload.get("updated_at") or datetime.now(tz=UTC).isoformat()),
        )


def snapshot_path(project_dir: Path) -> Path:
    """Return the snapshot file path inside a Flutter project."""
    return project_dir / SNAPSHOT_DIR_NAME / SNAPSHOT_FILE_NAME


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def hash_clean_tree(tree: CleanDesignTreeNode) -> str:
    """Hash the full clean design tree."""
    return _hash_payload(tree.model_dump(mode="json", by_alias=True))


def hash_colors(colors: dict[str, str]) -> str:
    """Hash color token payload."""
    return _hash_payload(dict(sorted(colors.items())))


def hash_typography(typography: dict[str, object]) -> str:
    """Hash typography token payload."""
    payload = {
        name: style.model_dump(mode="json", by_alias=True)
        for name, style in sorted(typography.items())
    }
    return _hash_payload(payload)


def hash_spacing(spacing: dict[str, float]) -> str:
    """Hash spacing token payload."""
    return _hash_payload(dict(sorted(spacing.items())))


def hash_tokens(tokens: DesignTokens) -> tuple[str, str, str]:
    """Return hashes for colors, typography, and spacing token groups."""
    return (
        hash_colors(tokens.colors),
        hash_typography(tokens.typography),
        hash_spacing(tokens.spacing),
    )


def hash_file_contents(content: str) -> str:
    """Hash generated file contents."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SnapshotLoadOutcome:
    """Result of loading ``snapshot.json`` from a Flutter project."""

    snapshot: GenerationSnapshot | None
    quarantined_path: Path | None = None


def load_snapshot(
    project_dir: Path,
    *,
    fail_on_corrupt: bool = False,
) -> SnapshotLoadOutcome:
    """Load a persisted snapshot when present and valid.

    Args:
        project_dir: Flutter project root.
        fail_on_corrupt: When True, raise instead of quarantining and returning empty.

    Returns:
        Outcome with snapshot (or ``None``) and optional quarantine path.

    Raises:
        FlutterProjectError: When ``fail_on_corrupt`` is True and the snapshot file is invalid.
    """
    path = snapshot_path(project_dir)
    if not path.is_file():
        return SnapshotLoadOutcome(snapshot=None)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("snapshot payload must be a JSON object")
        return SnapshotLoadOutcome(snapshot=GenerationSnapshot.from_dict(payload))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        corrupt_path = path.with_suffix(".json.corrupt")
        try:
            path.replace(corrupt_path)
        except OSError:
            logger.exception("Failed to quarantine corrupt snapshot at {}", path)
        message = (
            f"Corrupt incremental sync snapshot quarantined to {corrupt_path}. "
            "Delete .figma-flutter/ or re-run generate to rebuild sync state."
        )
        if fail_on_corrupt:
            raise FlutterProjectError(message) from exc
        logger.warning("{} ({})", message, exc)
        return SnapshotLoadOutcome(snapshot=None, quarantined_path=corrupt_path)


@contextlib.contextmanager
def _snapshot_write_lock(path: Path) -> Iterator[None]:
    """Exclusive lock for snapshot read-check-write (cross-thread and cross-process)."""
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via a same-directory temp file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    encoded = content.encode("utf-8")
    try:
        with tmp_path.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.is_file():
            tmp_path.unlink(missing_ok=True)


def save_snapshot(
    project_dir: Path,
    snapshot: GenerationSnapshot,
    *,
    expected_version: int | None = None,
) -> None:
    """Persist the latest generation snapshot with optimistic concurrency.

    Args:
        project_dir: Flutter project root.
        snapshot: Snapshot payload to write (``version`` should be ``expected_version + 1``).
        expected_version: When set, the on-disk snapshot must still have this ``version``
            or a ``SnapshotConflictError`` is raised.

    Raises:
        SnapshotConflictError: When another process updated the snapshot first.
    """
    path = snapshot_path(project_dir)
    with _snapshot_write_lock(path):
        if expected_version is not None and path.is_file():
            current = load_snapshot(project_dir).snapshot
            if current is not None and current.version != expected_version:
                raise SnapshotConflictError(
                    f"Snapshot version conflict: expected {expected_version}, "
                    f"found {current.version} at {path}. Re-run generate without parallel writers."
                )
        snapshot.updated_at = datetime.now(tz=UTC).isoformat()
        payload = json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False)
        _atomic_write_text(path, payload)
