"""One-time migration from legacy ``.figma-flutter``, agent ``logs/``, and flat ``reference/`` layouts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import agent_repo_root
from figma_flutter_agent.debug.mirror import FIGMA_DEBUG_LOG_DIR, project_mirror_label
from figma_flutter_agent.debug.paths import (
    _IR_STAGE_FILENAMES,
    ARTIFACT_LAYOUT_MARKER,
    ARTIFACT_LAYOUT_MARKER_V2,
    ARTIFACT_LAYOUT_VERSION,
    DART_BUG_DIR,
    DART_DIR,
    DEBUG_CAPTURE_DIR,
    EMITTER_META_JSON,
    EMITTER_REF_DART,
    FIGMA_DEBUG_DIR,
    FIGMA_FLUTTER_META_DIR,
    FIGMA_JSON,
    FIGMA_PNG,
    FIGMA_REFERENCE_SUBDIR,
    IR_DIR,
    LEGACY_AGENT_DIR,
    LEGACY_CAPTURE_SANDBOX_DIR,
    LEGACY_FIGMA_DEBUG_DIR,
    PERF_SUBDIR,
    PLAN_DART,
    PRIMARY_DIR,
    PROCESSED_DIR,
    PROCESSED_JSON,
    PROVENANCE_DIR,
    PROVENANCE_JSON,
    RAW_DIR,
    RAW_JSON,
    REFERENCE_DIR,
    RENDERS_SUBDIR,
    REPORTS_DIR,
    RENDERS_SUBDIR,
    RUN_LOGS_SUBDIR,
    SCREEN_BUG_DART,
    SCREEN_DART,
    SECONDARY_CAPTURE_DIR,
    SECONDARY_DIR,
    SECONDARY_PERF_DIR,
    SEMANTICS_DIR,
    SEMANTICS_JSON,
    SHARED_DIR,
    SNAPSHOT_FILE_NAME,
    SYNC_DIR,
    WIZARD_STATE_FILE,
    WORKSPACE_STATE_FILE,
    CAPTURE_SANDBOX_SUBDIR,
    capture_sandbox_dir,
    debug_capture_artifact_path,
    emitter_reference_dir,
    legacy_project_layout_marker_path,
    legacy_project_layout_marker_v2_path,
    legacy_project_run_log_path,
    legacy_project_run_logs_dir,
    legacy_project_sync_snapshot_path,
    legacy_project_wizard_prefs_path,
    legacy_pubspec_resolve_stamp_path,
    legacy_v2_dart_debug_snapshot_path,
    legacy_v2_debug_capture_artifact_path,
    legacy_v2_emitter_reference_bundle_path,
    legacy_v2_figma_reference_png_path,
    legacy_v2_processed_dump_path,
    legacy_v2_raw_dump_path,
    legacy_v2_screen_ir_dump_path,
    legacy_workspace_prefs_path,
    project_layout_marker_path,
    project_meta_dir,
    project_run_log_path,
    project_wizard_prefs_path,
    pubspec_resolve_stamp_path,
    render_session_dir,
    screen_ir_dump_path,
    screen_perf_dir,
    screen_primary_dir,
    screen_root,
    screen_secondary_dir,
    shared_debug_dir,
    sync_snapshot_path,
    workspace_prefs_path,
)

_EMITTER_BUNDLE_SUFFIX = "_screen.dart"
_EMITTER_META_SUFFIX = "_reference.json"
_FIGMA_META_SUFFIX = "_figma.json"
_FIGMA_IMAGE_SUFFIX = "_figma.png"
_DEBUG_ROOT_SKIP_DIRS = frozenset(
    {
        SYNC_DIR,
        RUN_LOGS_SUBDIR,
        SHARED_DIR,
        DEBUG_CAPTURE_DIR,
        LEGACY_CAPTURE_SANDBOX_DIR,
        RAW_DIR,
        PROCESSED_DIR,
        IR_DIR,
        DART_DIR,
        DART_BUG_DIR,
        SEMANTICS_DIR,
        PROVENANCE_DIR,
        REPORTS_DIR,
        REFERENCE_DIR,
        PERF_SUBDIR,
        RENDERS_SUBDIR,
    },
)


def workspace_layout_marker_path(workspace_root: Path) -> Path:
    """Return the migration marker path under ``workspace_root/.figma-flutter/``."""
    return workspace_root / FIGMA_FLUTTER_META_DIR / "layout-version"


def _read_project_layout_version(project_dir: Path) -> int:
    for marker in (
        project_layout_marker_path(project_dir),
        legacy_project_layout_marker_path(project_dir),
        legacy_project_layout_marker_v2_path(project_dir),
    ):
        version = _read_layout_version(marker)
        if version > 0:
            return version
    return 0


def ensure_project_debug_layout(project_dir: Path) -> None:
    """Migrate legacy project artifacts once, then stamp the layout marker."""
    moved = migrate_project_debug_dir_rename(project_dir)
    version = _read_project_layout_version(project_dir)
    if version >= ARTIFACT_LAYOUT_VERSION:
        return
    if version < 2:
        moved += migrate_legacy_project_artifacts(project_dir)
    if version < 3:
        moved += migrate_agent_logs_into_project(project_dir)
    if version < 5:
        moved += migrate_capture_sandbox_nested_layout(project_dir)
    if version < 6:
        moved += migrate_screen_centric_layout(project_dir)
    if version < 7:
        moved += migrate_flat_screen_layout(project_dir)
    marker = project_layout_marker_path(project_dir)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"{ARTIFACT_LAYOUT_VERSION}\n", encoding="utf-8")
    for legacy_marker in (
        legacy_project_layout_marker_path(project_dir),
        legacy_project_layout_marker_v2_path(project_dir),
    ):
        if legacy_marker.is_file():
            legacy_marker.unlink()
    if moved:
        logger.info(
            "Migrated {} legacy artifact(s) into {}/ for {}",
            moved,
            FIGMA_DEBUG_DIR,
            project_dir.as_posix(),
        )


def ensure_workspace_debug_layout(workspace_root: Path) -> None:
    """Migrate legacy workspace prefs once, then stamp the layout marker."""
    migrate_workspace_debug_dir_rename(workspace_root)
    moved = _move_file(
        legacy_workspace_prefs_path(workspace_root),
        workspace_prefs_path(workspace_root),
    )
    marker = workspace_layout_marker_path(workspace_root)
    if marker.is_file():
        return
    moved += migrate_legacy_workspace_artifacts(workspace_root)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("2\n", encoding="utf-8")
    if moved:
        logger.info(
            "Migrated {} legacy workspace artifact(s) into {}/ for {}",
            moved,
            FIGMA_DEBUG_DIR,
            workspace_root.as_posix(),
        )


def migrate_agent_logs_into_project(project_dir: Path) -> int:
    """Move legacy agent-repo logs (figma-debug mirror, dart-errors, renders, perf) into ``.debug``.

    Args:
        project_dir: Flutter project root.

    Returns:
        Number of files moved.
    """
    moved = 0
    label = project_mirror_label(project_dir)
    mirror_root = agent_repo_root() / FIGMA_DEBUG_LOG_DIR / label
    debug_root = project_dir / FIGMA_DEBUG_DIR
    if mirror_root.is_dir():
        for path in sorted(mirror_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(mirror_root)
            if _move_file(path, debug_root / relative):
                moved += 1
        _remove_empty_tree(mirror_root)

    project_resolved = project_dir.resolve().as_posix()
    agent_root = agent_repo_root()
    dart_src = agent_root / "logs" / "dart-errors"
    if dart_src.is_dir():
        destination = legacy_project_run_logs_dir(project_dir)
        for log_file in sorted(dart_src.glob("*.jsonl")):
            if not _dart_error_log_matches_project(log_file, project_resolved):
                continue
            target = destination / "last.log"
            if target.is_file():
                target = destination / log_file.name
            if _move_file(log_file, target):
                moved += 1

    renders_src = agent_root / "logs" / "renders"
    if renders_src.is_dir():
        for session_dir in sorted(renders_src.iterdir()):
            if not session_dir.is_dir():
                continue
            if not _render_session_matches_project(session_dir, project_resolved):
                continue
            feature_name = _render_session_feature_name(session_dir)
            destination = render_session_dir(
                project_dir,
                session_dir.name,
                feature_name=feature_name,
            )
            for path in sorted(session_dir.rglob("*")):
                if path.is_file() and _move_file(path, destination / path.relative_to(session_dir)):
                    moved += 1
            _remove_empty_tree(session_dir)

    return moved


def migrate_project_debug_dir_rename(project_dir: Path) -> int:
    """Rename ``.figma_debug`` to ``.debug`` when the legacy directory still exists.

    Args:
        project_dir: Flutter project root.

    Returns:
        ``1`` when renamed or legacy removed, else ``0``.
    """
    legacy = project_dir / LEGACY_FIGMA_DEBUG_DIR
    if not legacy.is_dir():
        return 0
    destination = project_dir / FIGMA_DEBUG_DIR
    if destination.exists():
        shutil.rmtree(legacy)
        return 1
    shutil.move(str(legacy), str(destination))
    return 1


def migrate_workspace_debug_dir_rename(workspace_root: Path) -> int:
    """Rename workspace ``.figma_debug`` to ``.debug``."""
    return migrate_project_debug_dir_rename(workspace_root)


def migrate_capture_sandbox_nested_layout(project_dir: Path) -> int:
    """Move ``capture-sandbox`` into ``capture/sandbox`` under ``.debug``.

    Args:
        project_dir: Flutter project root.

    Returns:
        ``1`` when a tree was moved or removed, else ``0``.
    """
    legacy = project_dir / FIGMA_DEBUG_DIR / LEGACY_CAPTURE_SANDBOX_DIR
    if not legacy.is_dir():
        return 0
    destination = capture_sandbox_dir(project_dir)
    if destination.exists():
        shutil.rmtree(legacy)
        return 1
    if _move_tree(legacy, destination):
        return 1
    return 0


def migrate_legacy_project_artifacts(project_dir: Path) -> int:
    """Move legacy ``.figma-flutter`` and flat emitter reference files into ``.debug``.

    Args:
        project_dir: Flutter project root.

    Returns:
        Number of files or directories moved.
    """
    moved = 0
    legacy_root = project_dir / LEGACY_AGENT_DIR
    moved += _move_tree_children(
        legacy_root / "reference",
        project_dir / FIGMA_DEBUG_DIR / REFERENCE_DIR / "figma",
    )
    moved += _move_file(
        legacy_root / SNAPSHOT_FILE_NAME,
        legacy_project_sync_snapshot_path(project_dir),
    )
    moved += _move_tree(
        legacy_root / LEGACY_CAPTURE_SANDBOX_DIR,
        capture_sandbox_dir(project_dir),
    )
    moved += _move_file(
        legacy_root / WIZARD_STATE_FILE,
        legacy_project_wizard_prefs_path(project_dir),
    )
    moved += _migrate_flat_emitter_reference_dir(project_dir)
    _remove_empty_dir(legacy_root)
    return moved


def migrate_legacy_workspace_artifacts(workspace_root: Path) -> int:
    """Move legacy workspace prefs from ``.figma-flutter`` into ``.debug``.

    Args:
        workspace_root: Workspace root that owns one or more Flutter apps.

    Returns:
        Number of files moved.
    """
    legacy_root = workspace_root / LEGACY_AGENT_DIR
    moved = _move_file(
        legacy_root / WORKSPACE_STATE_FILE,
        workspace_prefs_path(workspace_root),
    )
    _remove_empty_dir(legacy_root)
    return moved


def migrate_screen_centric_layout(project_dir: Path) -> int:
    """Move v2 domain folders into ``.debug/<feature>/primary|secondary/``."""
    debug_root = project_dir / FIGMA_DEBUG_DIR
    if not debug_root.is_dir():
        return 0

    moved = 0
    features = _discover_v2_feature_slugs(debug_root)
    for feature in sorted(features):
        moved += _migrate_feature_v2_artifacts(project_dir, feature)

    shared_dir = shared_debug_dir(project_dir)
    raw_dir = debug_root / RAW_DIR
    if raw_dir.is_dir():
        for path in sorted(raw_dir.glob("full_file_*.json")):
            if _move_file(path, shared_dir / path.name):
                moved += 1

    # Root-level render sessions → per-feature secondary/renders when manifest names a feature.
    renders_root = debug_root / RENDERS_SUBDIR
    if renders_root.is_dir():
        for session_dir in sorted(renders_root.iterdir()):
            if not session_dir.is_dir():
                continue
            feature_name = _render_session_feature_name(session_dir)
            if feature_name is None:
                continue
            destination = render_session_dir(
                project_dir,
                session_dir.name,
                feature_name=feature_name,
            )
            if destination.exists():
                continue
            if _move_tree(session_dir, destination):
                moved += 1

    _remove_empty_tree(debug_root / RAW_DIR)
    _remove_empty_tree(debug_root / PROCESSED_DIR)
    _remove_empty_tree(debug_root / IR_DIR)
    _remove_empty_tree(debug_root / DART_DIR)
    _remove_empty_tree(debug_root / DART_BUG_DIR)
    _remove_empty_tree(debug_root / SEMANTICS_DIR)
    _remove_empty_tree(debug_root / PROVENANCE_DIR)
    _remove_empty_tree(debug_root / REPORTS_DIR)
    _remove_empty_tree(debug_root / REFERENCE_DIR)
    _remove_empty_tree(debug_root / PERF_SUBDIR)
    _remove_empty_tree(renders_root)
    return moved


def migrate_flat_screen_layout(project_dir: Path) -> int:
    """Flatten ``primary|secondary`` shards and evict non-screen ``.debug`` root files (v4 layout)."""
    debug_root = project_dir / FIGMA_DEBUG_DIR
    if not debug_root.is_dir():
        return 0

    moved = 0
    meta_pairs: list[tuple[Path, Path]] = [
        (legacy_project_wizard_prefs_path(project_dir), project_wizard_prefs_path(project_dir)),
        (legacy_pubspec_resolve_stamp_path(project_dir), pubspec_resolve_stamp_path(project_dir)),
        (
            legacy_project_layout_marker_path(project_dir),
            project_layout_marker_path(project_dir),
        ),
        (
            legacy_project_layout_marker_v2_path(project_dir),
            project_layout_marker_path(project_dir),
        ),
    ]
    for source, destination in meta_pairs:
        if source.is_file() and _move_file(source, destination):
            moved += 1

    legacy_shared = debug_root / SHARED_DIR
    if legacy_shared.is_dir():
        moved += _move_tree_children(legacy_shared, shared_debug_dir(project_dir))

    for legacy_capture in (
        debug_root / DEBUG_CAPTURE_DIR / CAPTURE_SANDBOX_SUBDIR,
        debug_root / LEGACY_CAPTURE_SANDBOX_DIR,
        debug_root / DEBUG_CAPTURE_DIR,
    ):
        if legacy_capture.is_dir() and legacy_capture != capture_sandbox_dir(project_dir):
            if capture_sandbox_dir(project_dir).exists():
                moved += _move_tree_children(legacy_capture, capture_sandbox_dir(project_dir))
                _remove_empty_tree(legacy_capture)
            elif _move_tree(legacy_capture, capture_sandbox_dir(project_dir)):
                moved += 1

    legacy_sync = legacy_project_sync_snapshot_path(project_dir)
    if legacy_sync.is_file():
        feature = _feature_name_from_snapshot_file(legacy_sync) or _active_screen_from_wizard(
            project_dir
        )
        if feature and _move_file(legacy_sync, sync_snapshot_path(project_dir, feature)):
            moved += 1
    legacy_sync_lock = legacy_sync.with_name(f"{legacy_sync.name}.lock")
    if legacy_sync_lock.is_file():
        legacy_sync_lock.unlink()
        moved += 1

    legacy_log = legacy_project_run_log_path(project_dir)
    if legacy_log.is_file():
        feature = _active_screen_from_wizard(project_dir) or "screen"
        if _move_file(legacy_log, project_run_log_path(project_dir, feature)):
            moved += 1

    for child in sorted(debug_root.iterdir()):
        if not child.is_dir():
            if child.name.startswith(".") and _move_file(child, project_meta_dir(project_dir) / child.name):
                moved += 1
            continue
        if child.name in _DEBUG_ROOT_SKIP_DIRS:
            _remove_empty_tree(child)
            continue
        moved += _flatten_screen_shard_dirs(child)

    for subdir in _DEBUG_ROOT_SKIP_DIRS:
        _remove_empty_tree(debug_root / subdir)

    return moved


def _feature_name_from_snapshot_file(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    feature = payload.get("feature_name")
    if isinstance(feature, str) and feature.strip():
        return feature.strip()
    return None


def _active_screen_from_wizard(project_dir: Path) -> str | None:
    for prefs_path in (
        project_wizard_prefs_path(project_dir),
        legacy_project_wizard_prefs_path(project_dir),
    ):
        if not prefs_path.is_file():
            continue
        try:
            for line in prefs_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("active_screen:"):
                    value = stripped.split(":", 1)[1].strip().strip("'\"")
                    return value or None
        except OSError:
            continue
    return None


def _flatten_screen_shard_dirs(screen_dir: Path) -> int:
    moved = 0
    for shard in (PRIMARY_DIR, SECONDARY_DIR):
        shard_dir = screen_dir / shard
        if not shard_dir.is_dir():
            continue
        capture_dir = shard_dir / SECONDARY_CAPTURE_DIR
        if capture_dir.is_dir():
            for path in sorted(capture_dir.iterdir()):
                if path.is_file() and _move_file(path, screen_dir / path.name):
                    moved += 1
            _remove_empty_tree(capture_dir)
        renders_dir = shard_dir / RENDERS_SUBDIR
        if renders_dir.is_dir():
            destination = screen_dir / RENDERS_SUBDIR
            moved += _move_tree_children(renders_dir, destination)
            _remove_empty_tree(renders_dir)
        perf_dir_path = shard_dir / SECONDARY_PERF_DIR
        if perf_dir_path.is_dir():
            destination = screen_dir / SECONDARY_PERF_DIR
            moved += _move_tree_children(perf_dir_path, destination)
            _remove_empty_tree(perf_dir_path)
        for path in sorted(shard_dir.iterdir()):
            if path.is_file() and _move_file(path, screen_dir / path.name):
                moved += 1
        _remove_empty_tree(shard_dir)
    return moved


def _discover_v2_feature_slugs(debug_root: Path) -> set[str]:
    features: set[str] = set()

    raw_dir = debug_root / RAW_DIR
    if raw_dir.is_dir():
        for path in raw_dir.glob("*_layout.json"):
            features.add(path.name[: -len("_layout.json")])

    processed_dir = debug_root / PROCESSED_DIR
    if processed_dir.is_dir():
        for path in processed_dir.glob("*_layout.json"):
            features.add(path.name[: -len("_layout.json")])

    ir_dir = debug_root / IR_DIR
    if ir_dir.is_dir():
        stage_suffixes = tuple(sorted(_IR_STAGE_FILENAMES, key=len, reverse=True))
        for path in ir_dir.glob("*.json"):
            stem = path.stem
            for stage in stage_suffixes:
                token = f"_{stage}"
                if stem.endswith(token):
                    features.add(stem[: -len(token)])
                    break

    dart_dir = debug_root / DART_DIR
    if dart_dir.is_dir():
        for path in dart_dir.glob("*_plan.dart"):
            features.add(path.name[: -len("_plan.dart")])
        for path in dart_dir.glob("*_screen.dart"):
            features.add(path.name[: -len("_screen.dart")])

    bug_dir = debug_root / DART_BUG_DIR
    if bug_dir.is_dir():
        for path in bug_dir.glob("*_screen.dart"):
            features.add(path.name[: -len("_screen.dart")])

    semantics_dir = debug_root / SEMANTICS_DIR
    if semantics_dir.is_dir():
        for path in semantics_dir.glob("*.json"):
            features.add(path.stem)

    provenance_dir = debug_root / PROVENANCE_DIR
    if provenance_dir.is_dir():
        for path in provenance_dir.glob("*.json"):
            features.add(path.stem)

    reports_dir = debug_root / REPORTS_DIR
    if reports_dir.is_dir():
        for path in reports_dir.glob("*_ai_ux.json"):
            features.add(path.name[: -len("_ai_ux.json")])
        for path in reports_dir.glob("*_animations.json"):
            features.add(path.name[: -len("_animations.json")])
        for path in reports_dir.glob("*_design_coverage.json"):
            features.add(path.name[: -len("_design_coverage.json")])

    figma_ref_dir = debug_root / REFERENCE_DIR / "figma"
    if figma_ref_dir.is_dir():
        for path in figma_ref_dir.glob("*_figma.png"):
            features.add(path.name[: -len("_figma.png")])

    emitter_dir = debug_root / REFERENCE_DIR / "emitter"
    if emitter_dir.is_dir():
        for path in emitter_dir.glob("*_screen.dart"):
            features.add(path.name[: -len("_screen.dart")])

    capture_root = debug_root / DEBUG_CAPTURE_DIR
    if capture_root.is_dir():
        for path in capture_root.glob("*_flutter_render.png"):
            features.add(path.name[: -len("_flutter_render.png")])
        for path in capture_root.glob("*_capture.json"):
            features.add(path.name[: -len("_capture.json")])

    perf_dir_path = debug_root / PERF_SUBDIR
    if perf_dir_path.is_dir():
        for path in perf_dir_path.glob("golden_capture_*.json"):
            label = path.stem.removeprefix("golden_capture_")
            if label:
                features.add(label.split("_ru_dirty")[0].split("_")[0])

    return features


def _migrate_feature_v2_artifacts(project_dir: Path, feature: str) -> int:
    moved = 0
    primary = screen_primary_dir(project_dir, feature)
    secondary = screen_secondary_dir(project_dir, feature)

    pairs: list[tuple[Path, Path]] = [
        (legacy_v2_raw_dump_path(project_dir, feature), primary / RAW_JSON),
        (legacy_v2_processed_dump_path(project_dir, feature), primary / PROCESSED_JSON),
        (
            legacy_v2_dart_debug_snapshot_path(project_dir, feature, "plan"),
            primary / PLAN_DART,
        ),
        (
            legacy_v2_dart_debug_snapshot_path(project_dir, feature, "final"),
            primary / SCREEN_DART,
        ),
        (
            legacy_v2_figma_reference_png_path(project_dir, feature),
            primary / FIGMA_PNG,
        ),
        (
            project_dir
            / FIGMA_DEBUG_DIR
            / FIGMA_REFERENCE_SUBDIR
            / f"{feature}_figma.json",
            primary / FIGMA_JSON,
        ),
        (
            project_dir / FIGMA_DEBUG_DIR / SEMANTICS_DIR / f"{feature}.json",
            primary / SEMANTICS_JSON,
        ),
        (
            legacy_v2_dart_debug_snapshot_path(project_dir, feature, "bug"),
            secondary / SCREEN_BUG_DART,
        ),
        (
            legacy_v2_emitter_reference_bundle_path(project_dir, feature),
            secondary / EMITTER_REF_DART,
        ),
        (
            emitter_reference_dir(project_dir) / f"{feature}_reference.json",
            secondary / EMITTER_META_JSON,
        ),
        (
            project_dir / FIGMA_DEBUG_DIR / PROVENANCE_DIR / f"{feature}.json",
            secondary / PROVENANCE_JSON,
        ),
        (
            project_dir / FIGMA_DEBUG_DIR / REPORTS_DIR / f"{feature}_ai_ux.json",
            secondary / "ai_ux.json",
        ),
        (
            project_dir / FIGMA_DEBUG_DIR / REPORTS_DIR / f"{feature}_animations.json",
            secondary / "animations.json",
        ),
        (
            project_dir / FIGMA_DEBUG_DIR / REPORTS_DIR / f"{feature}_design_coverage.json",
            secondary / "design_coverage.json",
        ),
    ]

    for stage in _IR_STAGE_FILENAMES:
        pairs.append(
            (
                legacy_v2_screen_ir_dump_path(project_dir, feature, stage),
                screen_ir_dump_path(project_dir, feature, stage),
            ),
        )

    for artifact in ("flutter_render", "preview_capture", "diff_heatmap", "manifest"):
        pairs.append(
            (
                legacy_v2_debug_capture_artifact_path(project_dir, feature, artifact),
                debug_capture_artifact_path(project_dir, feature, artifact),
            ),
        )

    perf_source = project_dir / FIGMA_DEBUG_DIR / PERF_SUBDIR
    if perf_source.is_dir():
        for path in sorted(perf_source.glob(f"golden_capture_{feature}*.json")):
            pairs.append((path, screen_perf_dir(project_dir, feature) / path.name))

    for source, destination in pairs:
        if source.is_file() and _move_file(source, destination):
            moved += 1

    return moved


def _migrate_flat_emitter_reference_dir(project_dir: Path) -> int:
    """Move emitter bundles from flat ``reference/`` into ``reference/emitter/``."""
    flat_dir = project_dir / FIGMA_DEBUG_DIR / REFERENCE_DIR
    if not flat_dir.is_dir():
        return 0
    destination = emitter_reference_dir(project_dir)
    moved = 0
    for path in sorted(flat_dir.iterdir()):
        if path.is_dir():
            continue
        if not (
            path.name.endswith(_EMITTER_BUNDLE_SUFFIX)
            or path.name.endswith(_EMITTER_META_SUFFIX)
        ):
            continue
        if _move_file(path, destination / path.name):
            moved += 1
    return moved


def _render_session_feature_name(session_dir: Path) -> str | None:
    manifest = session_dir / "manifest.jsonl"
    if not manifest.is_file():
        return None
    try:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            feature = payload.get("featureName") or payload.get("feature")
            if isinstance(feature, str) and feature.strip():
                return feature.strip()
    except (json.JSONDecodeError, OSError):
        return None
    return None


def _move_tree_children(source: Path, destination: Path) -> int:
    if not source.is_dir():
        return 0
    destination.mkdir(parents=True, exist_ok=True)
    moved = 0
    for child in sorted(source.iterdir()):
        if _move_file(child, destination / child.name) or _move_tree(child, destination / child.name):
            moved += 1
    _remove_empty_dir(source)
    return moved


def _move_tree(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return True


def _move_file(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    if destination.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return True


def _remove_empty_dir(path: Path) -> None:
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()


def _remove_empty_tree(path: Path) -> None:
    if not path.is_dir():
        return
    for child in sorted(path.iterdir(), reverse=True):
        if child.is_dir():
            _remove_empty_tree(child)
        elif child.is_file():
            continue
    _remove_empty_dir(path)


def _read_layout_version(marker: Path) -> int:
    if not marker.is_file():
        return 0
    try:
        return int(marker.read_text(encoding="utf-8").strip() or "0")
    except ValueError:
        return 0


def _dart_error_log_matches_project(log_file: Path, project_resolved: str) -> bool:
    try:
        first_line = log_file.read_text(encoding="utf-8").splitlines()[0]
        payload = json.loads(first_line)
    except (IndexError, json.JSONDecodeError, OSError):
        return False
    logged = payload.get("projectDir")
    if not isinstance(logged, str):
        return False
    return Path(logged).resolve().as_posix() == project_resolved


def _render_session_matches_project(session_dir: Path, project_resolved: str) -> bool:
    manifest = session_dir / "manifest.jsonl"
    if not manifest.is_file():
        return False
    try:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            logged = payload.get("projectDir")
            if isinstance(logged, str) and Path(logged).resolve().as_posix() == project_resolved:
                return True
    except (json.JSONDecodeError, OSError):
        return False
    return False
