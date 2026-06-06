"""Canonical paths for ``.figma_debug`` raw and processed screen dumps."""

from __future__ import annotations

from pathlib import Path

FIGMA_DEBUG_DIR = ".figma_debug"
RAW_DIR = "raw"
PROCESSED_DIR = "processed"
DART_DIR = "dart"
DART_BUG_DIR = "dart.bug"
IR_DIR = "ir"
REFERENCE_DIR = "reference"


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


def emitter_reference_bundle_path(project_dir: Path, feature_name: str) -> Path:
    """Return the IR emitter golden bundle path for ``feature_name``.

    Mirrors ``.figma_debug/dart/<feature>_screen.dart`` but under ``reference/``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug aligned with ``<feature>_layout.json``.

    Returns:
        Path under ``.figma_debug/reference/<feature>_screen.dart``.
    """
    return (
        project_dir
        / FIGMA_DEBUG_DIR
        / REFERENCE_DIR
        / f"{feature_name}_screen.dart"
    )


def emitter_reference_layout_path(project_dir: Path, feature_name: str) -> Path:
    """Deprecated alias for the single-file emitter bundle path."""
    return emitter_reference_bundle_path(project_dir, feature_name)


def emitter_reference_dir(project_dir: Path) -> Path:
    """Return ``.figma_debug/reference`` for emitter golden artifacts."""
    return project_dir / FIGMA_DEBUG_DIR / REFERENCE_DIR


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


def rename_screen_debug_artifacts(
    project_dir: Path,
    old_feature: str,
    new_feature: str,
) -> int:
    """Move on-disk ``.figma_debug`` artifacts when a manifest feature slug changes.

    Args:
        project_dir: Flutter project root.
        old_feature: Previous screen feature slug.
        new_feature: New screen feature slug.

    Returns:
        Number of files moved on disk.
    """
    import shutil

    if old_feature == new_feature:
        return 0

    moves: list[tuple[Path, Path]] = []
    for resolver in (raw_dump_path, processed_dump_path):
        old_path = resolver(project_dir, old_feature)
        if old_path.is_file():
            moves.append((old_path, resolver(project_dir, new_feature)))

    for snapshot in ("plan", "final", "bug"):
        old_path = dart_debug_snapshot_path(project_dir, old_feature, snapshot)
        if old_path.is_file():
            moves.append(
                (old_path, dart_debug_snapshot_path(project_dir, new_feature, snapshot)),
            )

    old_reference = emitter_reference_bundle_path(project_dir, old_feature)
    if old_reference.is_file():
        moves.append(
            (old_reference, emitter_reference_bundle_path(project_dir, new_feature)),
        )

    ir_dir = project_dir / FIGMA_DEBUG_DIR / IR_DIR
    if ir_dir.is_dir():
        prefix = f"{old_feature}_"
        for old_ir in ir_dir.glob(f"{old_feature}_*.json"):
            suffix = old_ir.name[len(prefix) :]
            moves.append((old_ir, ir_dir / f"{new_feature}_{suffix}"))

    reports_dir = project_dir / FIGMA_DEBUG_DIR / "reports"
    for suffix in ("_ai_ux.json",):
        old_report = reports_dir / f"{old_feature}{suffix}"
        if old_report.is_file():
            moves.append((old_report, reports_dir / f"{new_feature}{suffix}"))

    moved = 0
    for source, destination in moves:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file():
            destination.unlink()
        shutil.move(str(source), str(destination))
        moved += 1
    return moved


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
