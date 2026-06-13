"""One-time migration from legacy ``.figma-flutter``, agent ``logs/``, and flat ``reference/`` layouts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import agent_repo_root
from figma_flutter_agent.debug.mirror import FIGMA_DEBUG_LOG_DIR, project_mirror_label
from figma_flutter_agent.debug.paths import (
    FIGMA_DEBUG_DIR,
    LEGACY_AGENT_DIR,
    LEGACY_CAPTURE_SANDBOX_DIR,
    LEGACY_FIGMA_DEBUG_DIR,
    REFERENCE_DIR,
    SNAPSHOT_FILE_NAME,
    WIZARD_STATE_FILE,
    WORKSPACE_STATE_FILE,
    capture_sandbox_dir,
    emitter_reference_dir,
    figma_reference_dir,
    project_run_logs_dir,
    project_wizard_prefs_path,
    render_session_dir,
    sync_snapshot_path,
    workspace_prefs_path,
)

ARTIFACT_LAYOUT_MARKER = ".artifact-layout-v2"
ARTIFACT_LAYOUT_VERSION = 5
_EMITTER_BUNDLE_SUFFIX = "_screen.dart"
_EMITTER_META_SUFFIX = "_reference.json"
_FIGMA_META_SUFFIX = "_figma.json"
_FIGMA_IMAGE_SUFFIX = "_figma.png"


def project_layout_marker_path(project_dir: Path) -> Path:
    """Return the migration marker path under ``project_dir/.debug/``."""
    return project_dir / FIGMA_DEBUG_DIR / ARTIFACT_LAYOUT_MARKER


def workspace_layout_marker_path(workspace_root: Path) -> Path:
    """Return the migration marker path under ``workspace_root/.debug/``."""
    return workspace_root / FIGMA_DEBUG_DIR / ARTIFACT_LAYOUT_MARKER


def ensure_project_debug_layout(project_dir: Path) -> None:
    """Migrate legacy project artifacts once, then stamp the layout marker."""
    moved = migrate_project_debug_dir_rename(project_dir)
    marker = project_layout_marker_path(project_dir)
    version = _read_layout_version(marker)
    if version >= ARTIFACT_LAYOUT_VERSION:
        return
    if version < 2:
        moved += migrate_legacy_project_artifacts(project_dir)
    if version < 3:
        moved += migrate_agent_logs_into_project(project_dir)
    if version < ARTIFACT_LAYOUT_VERSION:
        moved += migrate_capture_sandbox_nested_layout(project_dir)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"{ARTIFACT_LAYOUT_VERSION}\n", encoding="utf-8")
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
    marker = workspace_layout_marker_path(workspace_root)
    if marker.is_file():
        return
    moved = migrate_legacy_workspace_artifacts(workspace_root)
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
        destination = project_run_logs_dir(project_dir)
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
            destination = render_session_dir(project_dir, session_dir.name)
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
        figma_reference_dir(project_dir),
    )
    moved += _move_file(
        legacy_root / SNAPSHOT_FILE_NAME,
        sync_snapshot_path(project_dir),
    )
    moved += _move_tree(
        legacy_root / LEGACY_CAPTURE_SANDBOX_DIR,
        capture_sandbox_dir(project_dir),
    )
    moved += _move_file(
        legacy_root / WIZARD_STATE_FILE,
        project_wizard_prefs_path(project_dir),
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
