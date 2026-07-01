"""Repair worktree discovery and menu labels for the wizard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.checkpoint import load_last_checkpoint
from figma_flutter_agent.dev.opencode.worktree import list_repair_worktree_dirs


@dataclass(frozen=True)
class RepairWorktreeEntry:
    """One selectable repair worktree for the active project screen."""

    case_id: str
    worktree: Path
    project_label: str
    feature: str
    last_step: str | None
    loop_round: int | None
    mtime: float

    @property
    def menu_label(self) -> str:
        """Human-readable wizard menu line."""
        step = self.last_step or "new"
        round_hint = f" cycle {self.loop_round}" if self.loop_round else ""
        return f"{self.case_id} — last: {step}{round_hint}"


def load_repair_manifest(worktree: Path) -> dict[str, Any]:
    """Load ``.repair/manifest.json`` when present."""
    manifest_path = worktree / ".repair" / "manifest.json"
    if not manifest_path.is_file():
        return {}
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def list_repair_worktrees_for_screen(
    repo: Path,
    *,
    project_label: str,
    feature: str,
) -> list[RepairWorktreeEntry]:
    """Return repair worktrees matching ``project_label`` and ``feature``.

    Args:
        repo: Agent git repository root.
        project_label: Sanitized Flutter project folder label.
        feature: Screen feature slug.

    Returns:
        Newest-first list of worktree entries with repair manifests.
    """
    entries: list[RepairWorktreeEntry] = []
    for worktree in list_repair_worktree_dirs(repo):
        manifest = load_repair_manifest(worktree)
        if manifest.get("project") != project_label:
            continue
        if manifest.get("feature") != feature:
            continue
        state_dir = worktree / ".repair" / "state"
        checkpoint = load_last_checkpoint(state_dir)
        last_step = str(checkpoint.get("step")) if checkpoint else None
        loop_round = (
            int(checkpoint["loop_round"]) if checkpoint and checkpoint.get("loop_round") else None
        )
        entries.append(
            RepairWorktreeEntry(
                case_id=str(manifest.get("case_id") or worktree.name),
                worktree=worktree,
                project_label=project_label,
                feature=feature,
                last_step=last_step,
                loop_round=loop_round,
                mtime=worktree.stat().st_mtime,
            )
        )
    entries.sort(key=lambda item: item.mtime, reverse=True)
    return entries


def resolve_worktree_screen_bundle(worktree: Path) -> Path:
    """Return ``screen.dart`` or ``plan.dart`` from a worktree debug mirror.

    Args:
        worktree: Repair git worktree root.

    Returns:
        Path to an on-disk Dart bundle under ``.repair/debug/``.

    Raises:
        FileNotFoundError: When no bundle exists in the worktree mirror.
    """
    manifest = load_repair_manifest(worktree)
    debug_rel = manifest.get("debug_mirror")
    if debug_rel:
        mirror = worktree / str(debug_rel)
    else:
        project = str(manifest.get("project") or "")
        feature = str(manifest.get("feature") or "")
        mirror = worktree / ".repair" / "debug" / project / feature
    for name in ("screen.dart", "plan.dart"):
        candidate = mirror / name
        if candidate.is_file():
            return candidate
    msg = f"No screen.dart or plan.dart under {mirror.as_posix()}"
    raise FileNotFoundError(msg)
