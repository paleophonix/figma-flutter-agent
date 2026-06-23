"""Isolated Flutter project copy for repair regenerate and capture verify."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.dev.opencode.repair_log import emit_repair_progress
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace

_SANDBOX_REL = Path("candidate") / "flutter_project"
_MANIFEST_SANDBOX_KEY = "sandbox_project_dir"
_MANIFEST_SOURCE_KEY = "source_project_dir"
_COPY_IGNORE = shutil.ignore_patterns(".dart_tool", "build", ".git")


def sandbox_project_dir(workspace: RepairWorkspace) -> Path:
    """Return the repair-local Flutter project sandbox path."""
    return workspace.repair_root / _SANDBOX_REL


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        return {}
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _persist_manifest_paths(
    manifest_path: Path,
    *,
    source_project_dir: Path,
    sandbox_dir: Path,
) -> None:
    manifest = _load_manifest(manifest_path)
    manifest[_MANIFEST_SOURCE_KEY] = source_project_dir.resolve().as_posix()
    manifest[_MANIFEST_SANDBOX_KEY] = sandbox_dir.resolve().as_posix()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_sandbox_project_dir(manifest_path: Path) -> Path | None:
    """Return persisted sandbox project dir when present on disk."""
    raw = _load_manifest(manifest_path).get(_MANIFEST_SANDBOX_KEY)
    if raw is None:
        return None
    candidate = Path(str(raw))
    return candidate if candidate.is_dir() else None


def ensure_flutter_project_sandbox(
    workspace: RepairWorkspace,
    source_project_dir: Path,
) -> Path:
    """Materialize or refresh a repair-local Flutter project sandbox.

    Args:
        workspace: Active repair workspace.
        source_project_dir: User Flutter project root (never written by repair verify).

    Returns:
        Path to ``.repair/candidate/flutter_project`` inside the worktree.
    """
    source = source_project_dir.resolve()
    dest = sandbox_project_dir(workspace)
    emit_repair_progress(
        "sandbox",
        f"Copying Flutter project into repair sandbox ({source.name})…",
    )
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, ignore=_COPY_IGNORE)
    emit_repair_progress("sandbox", "Flutter sandbox copy finished.")
    _persist_manifest_paths(
        workspace.manifest_path,
        source_project_dir=source,
        sandbox_dir=dest,
    )
    logger.info(
        "Repair flutter sandbox ready source={} sandbox={}",
        source.as_posix(),
        dest.as_posix(),
    )
    return dest


def resolve_repair_flutter_project_dir(
    workspace: RepairWorkspace,
    source_project_dir: Path,
) -> Path:
    """Return sandbox project dir for repair pipeline side effects."""
    existing = read_sandbox_project_dir(workspace.manifest_path)
    if existing is not None:
        return existing
    return ensure_flutter_project_sandbox(workspace, source_project_dir)
