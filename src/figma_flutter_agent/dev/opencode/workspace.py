"""Repair workspace layout under git worktree."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.debug.paths import screen_debug_safe_project, screen_root
from figma_flutter_agent.dev.opencode.run_gate import RunGateResult
from figma_flutter_agent.dev.opencode.worktree import create_repair_worktree


@dataclass(frozen=True)
class RepairWorkspace:
    """Resolved repair case workspace."""

    case_id: str
    worktree: Path
    repair_root: Path
    state_dir: Path
    debug_mirror: Path
    manifest_path: Path


def prepare_workspace(
    *,
    project_dir: Path,
    feature: str,
    gate: RunGateResult,
) -> RepairWorkspace:
    """Create worktree and copy debug bundle into ``.repair/debug/``."""
    case_id = uuid.uuid4().hex[:12]
    worktree = create_repair_worktree(agent_repo_root(), case_id)
    repair_root = worktree / ".repair"
    state_dir = repair_root / "state"
    project_label = screen_debug_safe_project(project_dir)
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
