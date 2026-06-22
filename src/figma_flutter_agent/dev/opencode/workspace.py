"""Repair workspace layout under git worktree."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.debug.paths import screen_debug_safe_project, screen_root
from figma_flutter_agent.dev.opencode.run_gate import RunGateResult
from figma_flutter_agent.dev.opencode.worktree import (
    allocate_repair_case_id,
    create_repair_worktree,
)
from figma_flutter_agent.observability import new_run_id

WORKTREE_TRACE_ID_KEY = "posthog_trace_id"


@dataclass(frozen=True)
class RepairWorkspace:
    """Resolved repair case workspace."""

    case_id: str
    worktree: Path
    repair_root: Path
    state_dir: Path
    debug_mirror: Path
    manifest_path: Path


def load_worktree_trace_id(manifest_path: Path) -> str | None:
    """Return persisted PostHog trace id from ``.repair/manifest.json`` when set."""
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        return None
    raw = manifest.get(WORKTREE_TRACE_ID_KEY)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def assign_worktree_trace_id(manifest_path: Path, *, trace_id: str | None = None) -> str:
    """Persist PostHog trace id on the worktree manifest (create when missing).

    Args:
        manifest_path: Path to ``.repair/manifest.json``.
        trace_id: Optional explicit id; generated when absent and not already stored.

    Returns:
        The active trace id for this repair worktree.
    """
    manifest: dict[str, object] = {}
    if manifest_path.is_file():
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            manifest = loaded
    existing = load_worktree_trace_id(manifest_path)
    if existing:
        return existing
    resolved = trace_id or new_run_id()
    manifest[WORKTREE_TRACE_ID_KEY] = resolved
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return resolved


def prepare_workspace(
    *,
    project_dir: Path,
    feature: str,
    gate: RunGateResult,
) -> RepairWorkspace:
    """Create worktree and copy debug bundle into ``.repair/debug/``."""
    project_label = screen_debug_safe_project(project_dir)
    repo = agent_repo_root()
    case_id = allocate_repair_case_id(
        repo,
        project_label=project_label,
        feature=feature,
    )
    worktree = create_repair_worktree(repo, case_id)
    repair_root = worktree / ".repair"
    state_dir = repair_root / "state"
    debug_mirror = repair_root / "debug" / project_label / feature
    state_dir.mkdir(parents=True, exist_ok=True)
    (repair_root / "reports").mkdir(parents=True, exist_ok=True)
    (repair_root / "candidate" / "planned_files").mkdir(parents=True, exist_ok=True)

    src = screen_root(project_dir, feature)
    if src.is_dir():
        if debug_mirror.exists():
            shutil.rmtree(debug_mirror)
        shutil.copytree(src, debug_mirror)

    manifest = {
        "case_id": case_id,
        "feature": feature,
        "project": project_label,
        "case_mode": gate.case_mode,
        "agent_board": gate.agent_board,
        "run_manifest": gate.to_manifest_dict(),
        "debug_mirror": debug_mirror.relative_to(worktree).as_posix(),
        WORKTREE_TRACE_ID_KEY: new_run_id(),
    }
    manifest_path = repair_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return RepairWorkspace(
        case_id=case_id,
        worktree=worktree,
        repair_root=repair_root,
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=manifest_path,
    )


def load_repair_workspace(worktree: Path) -> RepairWorkspace:
    """Attach an existing repair worktree without recreating debug mirrors.

    Args:
        worktree: Repair git worktree root containing ``.repair/manifest.json``.

    Returns:
        Resolved workspace paths for the repair case.

    Raises:
        FileNotFoundError: When ``.repair/manifest.json`` is missing.
    """
    repair_root = worktree / ".repair"
    manifest_path = repair_root / "manifest.json"
    if not manifest_path.is_file():
        msg = f"Repair manifest not found: {manifest_path.as_posix()}"
        raise FileNotFoundError(msg)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    case_id = str(manifest.get("case_id") or worktree.name)
    project_label = str(manifest.get("project") or "")
    feature = str(manifest.get("feature") or "")
    debug_rel = manifest.get("debug_mirror")
    if debug_rel:
        debug_mirror = worktree / str(debug_rel)
    else:
        debug_mirror = repair_root / "debug" / project_label / feature
    state_dir = repair_root / "state"
    return RepairWorkspace(
        case_id=case_id,
        worktree=worktree,
        repair_root=repair_root,
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=manifest_path,
    )
