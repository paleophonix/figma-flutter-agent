"""Canonical paths for ``.debug`` project artifacts."""

from __future__ import annotations

from pathlib import Path

FIGMA_DEBUG_DIR = ".debug"
LEGACY_FIGMA_DEBUG_DIR = ".figma_debug"
LEGACY_AGENT_DIR = ".figma-flutter"
RAW_DIR = "raw"
PROCESSED_DIR = "processed"
DART_DIR = "dart"
DART_BUG_DIR = "dart.bug"
IR_DIR = "ir"
REFERENCE_DIR = "reference"
FIGMA_REFERENCE_SUBDIR = f"{REFERENCE_DIR}/figma"
EMITTER_REFERENCE_SUBDIR = f"{REFERENCE_DIR}/emitter"
SYNC_DIR = "sync"
SNAPSHOT_FILE_NAME = "snapshot.json"
DEBUG_CAPTURE_DIR = "capture"
CAPTURE_SANDBOX_SUBDIR = "sandbox"
LEGACY_CAPTURE_SANDBOX_DIR = "capture-sandbox"
RUN_LOGS_SUBDIR = "logs"
LAST_RUN_LOG_FILE = "last.log"
LEGACY_DART_ERRORS_SUBDIR = "dart-errors"
LEGACY_TERMINAL_SUBDIR = "terminal"
RENDERS_SUBDIR = "renders"
PERF_SUBDIR = "perf"
WIZARD_STATE_FILE = "wizard-state.yml"
WORKSPACE_STATE_FILE = "workspace-state.yml"
FIGMA_REFERENCE_REL = f"{FIGMA_DEBUG_DIR}/{FIGMA_REFERENCE_SUBDIR}"
EMITTER_REFERENCE_REL = f"{FIGMA_DEBUG_DIR}/{EMITTER_REFERENCE_SUBDIR}"


def figma_reference_dir(project_dir: Path) -> Path:
    """Return ``.debug/reference/figma`` for Figma PNG/JSON visual gold."""
    return project_dir / FIGMA_DEBUG_DIR / FIGMA_REFERENCE_SUBDIR


def figma_reference_png_path(project_dir: Path, feature_name: str) -> Path:
    """Return the on-disk path for a feature Figma reference PNG."""
    return figma_reference_dir(project_dir) / f"{feature_name}_figma.png"


def figma_reference_metadata_path(project_dir: Path, feature_name: str) -> Path:
    """Return the on-disk path for a feature Figma reference JSON metadata."""
    return figma_reference_dir(project_dir) / f"{feature_name}_figma.json"


def legacy_figma_reference_dir(project_dir: Path) -> Path:
    """Return deprecated ``.figma-flutter/reference`` (pre-consolidation)."""
    return project_dir / LEGACY_AGENT_DIR / REFERENCE_DIR


def sync_snapshot_path(project_dir: Path) -> Path:
    """Return incremental sync snapshot path under ``.debug/sync/``."""
    return project_dir / FIGMA_DEBUG_DIR / SYNC_DIR / SNAPSHOT_FILE_NAME


def legacy_sync_snapshot_path(project_dir: Path) -> Path:
    """Return deprecated ``.figma-flutter/snapshot.json``."""
    return project_dir / LEGACY_AGENT_DIR / SNAPSHOT_FILE_NAME


def capture_sandbox_dir(project_dir: Path) -> Path:
    """Return warm golden capture sandbox under ``.debug/capture/sandbox``."""
    return debug_capture_root(project_dir) / CAPTURE_SANDBOX_SUBDIR


def debug_capture_safe_feature(feature_name: str) -> str:
    """Sanitize a feature slug for debug capture filenames."""
    return feature_name.replace("/", "_").replace("\\", "_")


def debug_capture_root(project_dir: Path) -> Path:
    """Return flat debug capture directory ``.debug/capture/``."""
    return project_dir / FIGMA_DEBUG_DIR / DEBUG_CAPTURE_DIR


def debug_capture_artifact_path(
    project_dir: Path,
    feature_name: str,
    artifact: str,
) -> Path:
    """Return a feature-prefixed capture artifact (Flutter render / diff / manifest only).

    Figma gold is canonical under :func:`figma_reference_png_path`, not duplicated here.
    """
    suffix_by_artifact = {
        "flutter_render": "_flutter_render.png",
        "diff_heatmap": "_diff_heatmap.png",
        "manifest": "_capture.json",
    }
    suffix = suffix_by_artifact.get(artifact)
    if suffix is None:
        msg = f"Unknown debug capture artifact {artifact!r}"
        raise ValueError(msg)
    safe_feature = debug_capture_safe_feature(feature_name)
    return debug_capture_root(project_dir) / f"{safe_feature}{suffix}"


def debug_capture_dir(project_dir: Path, feature_name: str) -> Path:
    """Return ``.debug/capture/`` (``feature_name`` ignored; kept for callers)."""
    _ = feature_name
    return debug_capture_root(project_dir)


def project_run_logs_dir(project_dir: Path) -> Path:
    """Return ``.debug/logs/`` for the latest pipeline subprocess + analyzer transcript."""
    return project_dir / FIGMA_DEBUG_DIR / RUN_LOGS_SUBDIR


def project_run_log_path(project_dir: Path) -> Path:
    """Return ``.debug/logs/last.log`` (cleared at each pipeline start)."""
    return project_run_logs_dir(project_dir) / LAST_RUN_LOG_FILE


def last_terminal_log_path(project_dir: Path) -> Path:
    """Deprecated alias for :func:`project_run_log_path`."""
    return project_run_log_path(project_dir)


def render_session_dir(project_dir: Path, log_stem: str) -> Path:
    """Return ``.debug/renders/<log_stem>/`` for combat-mode PNG sessions."""
    return project_dir / FIGMA_DEBUG_DIR / RENDERS_SUBDIR / log_stem


def perf_dir(project_dir: Path) -> Path:
    """Return ``.debug/perf/`` for golden capture phase timings."""
    return project_dir / FIGMA_DEBUG_DIR / PERF_SUBDIR


def project_wizard_prefs_path(project_dir: Path) -> Path:
    """Return wizard prefs for one Flutter project."""
    return project_dir / FIGMA_DEBUG_DIR / WIZARD_STATE_FILE


def workspace_prefs_path(workspace_root: Path) -> Path:
    """Return workspace-level wizard prefs under ``workspace_root/.debug/``."""
    return workspace_root / FIGMA_DEBUG_DIR / WORKSPACE_STATE_FILE


def legacy_workspace_prefs_path(workspace_root: Path) -> Path:
    """Return deprecated ``.figma-flutter/workspace-state.yml``."""
    return workspace_root / LEGACY_AGENT_DIR / WORKSPACE_STATE_FILE


def screen_ir_dump_path(project_dir: Path, feature_name: str, stage: str) -> Path:
    """Return the screen IR JSON snapshot path for ``feature_name`` and ``stage``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug (e.g. ``sign_up``).
        stage: Pipeline stage label (e.g. ``llm_parsed``, ``llm_validated``).

    Returns:
        Canonical path under ``.debug/ir/``.
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

    Mirrors ``.debug/dart/<feature>_screen.dart`` but under ``reference/``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug aligned with ``<feature>_layout.json``.

    Returns:
        Path under ``.debug/reference/emitter/<feature>_screen.dart``.
    """
    return emitter_reference_dir(project_dir) / f"{feature_name}_screen.dart"


def emitter_reference_layout_path(project_dir: Path, feature_name: str) -> Path:
    """Deprecated alias for the single-file emitter bundle path."""
    return emitter_reference_bundle_path(project_dir, feature_name)


def emitter_reference_dir(project_dir: Path) -> Path:
    """Return ``.debug/reference/emitter`` for emitter golden artifacts."""
    return project_dir / FIGMA_DEBUG_DIR / EMITTER_REFERENCE_SUBDIR


def legacy_emitter_reference_bundle_path(project_dir: Path, feature_name: str) -> Path:
    """Return deprecated flat ``.debug/reference/<feature>_screen.dart``."""
    return project_dir / FIGMA_DEBUG_DIR / REFERENCE_DIR / f"{feature_name}_screen.dart"


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
        Path under ``.debug/dart/`` or ``.debug/dart.bug/``.
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
    """Move on-disk ``.debug`` artifacts when a manifest feature slug changes.

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
