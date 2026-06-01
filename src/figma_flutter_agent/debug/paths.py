"""Canonical paths for ``.figma_debug`` raw and processed screen dumps."""

from __future__ import annotations

from pathlib import Path

FIGMA_DEBUG_DIR = ".figma_debug"
RAW_DIR = "raw"
PROCESSED_DIR = "processed"
DART_DIR = "dart"
DART_BUG_DIR = "dart.bug"
IR_DIR = "ir"


def screen_ir_dump_path(project_dir: Path, feature_name: str, stage: str) -> Path:
    """Return the screen IR JSON snapshot path for ``feature_name`` and ``stage``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug (e.g. ``sign_up``).
        stage: Pipeline stage label (e.g. ``llm_parsed``, ``llm_validated``).

    Returns:
        Canonical path under ``.figma_debug/ir/``.
    """
    return project_dir / FIGMA_DEBUG_DIR / IR_DIR / f"{feature_name}_{stage}.json"


def layout_debug_filename(feature_name: str) -> str:
    """Return the debug JSON basename aligned with ``lib/generated/<feature>_layout.dart``."""
    return f"{feature_name}_layout.json"


def raw_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return the raw Figma REST dump path for ``feature_name``."""
    return project_dir / FIGMA_DEBUG_DIR / RAW_DIR / layout_debug_filename(feature_name)


def processed_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return the parsed clean-tree dump path for ``feature_name``."""
    return project_dir / FIGMA_DEBUG_DIR / PROCESSED_DIR / layout_debug_filename(feature_name)


def dart_bundle_path(project_dir: Path, feature_name: str) -> Path:
    """Return the debug Dart bundle path for ``feature_name``."""
    return dart_debug_snapshot_path(project_dir, feature_name, "final")


def dart_debug_snapshot_path(project_dir: Path, feature_name: str, snapshot: str) -> Path:
    """Return a debug Dart bundle path for ``feature_name``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug.
        snapshot: ``plan`` (post-plan), ``final`` (pre-write), or ``bug`` (failed gate/analyze).

    Returns:
        Path under ``.figma_debug/dart/`` or ``.figma_debug/dart.bug/``.
    """
    if snapshot == "bug":
        return (
            project_dir
            / FIGMA_DEBUG_DIR
            / DART_BUG_DIR
            / f"{feature_name}_screen.dart"
        )
    if snapshot == "plan":
        return project_dir / FIGMA_DEBUG_DIR / DART_DIR / f"{feature_name}_plan.dart"
    if snapshot == "final":
        return project_dir / FIGMA_DEBUG_DIR / DART_DIR / f"{feature_name}_screen.dart"
    msg = f"Unknown dart debug snapshot {snapshot!r}; expected plan, final, or bug"
    raise ValueError(msg)


def full_file_dump_path(project_dir: Path, file_key: str) -> Path:
    """Return the full-file Figma dump path for ``file_key``."""
    return project_dir / FIGMA_DEBUG_DIR / RAW_DIR / f"full_file_{file_key}.json"


def legacy_raw_dump_path(project_dir: Path, node_id: str) -> Path:
    """Return the pre-layout raw dump path keyed by Figma node id."""
    return project_dir / FIGMA_DEBUG_DIR / f"raw_node_{node_id.replace(':', '_')}.json"


def legacy_full_file_dump_path(project_dir: Path, file_key: str) -> Path:
    """Return the legacy full-file dump path at the debug root."""
    return project_dir / FIGMA_DEBUG_DIR / f"full_file_{file_key}.json"


def resolve_full_file_dump(project_dir: Path, file_key: str) -> Path:
    """Resolve an existing full-file dump, preferring the ``raw/`` layout.

    Args:
        project_dir: Flutter project root.
        file_key: Figma file key.

    Returns:
        Path to an on-disk full-file dump.

    Raises:
        FileNotFoundError: When no cached full-file dump exists.
    """
    candidates = (
        full_file_dump_path(project_dir, file_key),
        legacy_full_file_dump_path(project_dir, file_key),
    )
    for path in candidates:
        if path.is_file():
            return path
    preferred = candidates[0]
    msg = (
        f"Full file dump not found at {preferred.as_posix()}. "
        "Run `figma-flutter batch dump-file` first."
    )
    raise FileNotFoundError(msg)


def resolve_screen_raw_dump(
    project_dir: Path,
    feature_name: str,
    node_id: str,
    *,
    explicit: Path | None = None,
) -> Path:
    """Resolve an existing per-screen raw dump path.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug.
        node_id: Figma node id for legacy fallback.
        explicit: Optional manifest ``dump`` path override.

    Returns:
        First matching on-disk path, or the preferred canonical path when missing.
    """
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    candidates.extend(
        (
            raw_dump_path(project_dir, feature_name),
            legacy_raw_dump_path(project_dir, node_id),
        )
    )
    for path in candidates:
        if path.is_file():
            return path
    return explicit or raw_dump_path(project_dir, feature_name)
