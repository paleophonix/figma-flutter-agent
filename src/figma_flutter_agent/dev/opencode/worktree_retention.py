"""Retention and orphan pruning for repair git worktrees."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.dev.opencode.worktree import (
    destroy_repair_worktree,
    list_repair_worktree_dirs,
    prune_orphaned_worktrees,
)


def apply_repair_worktree_retention(
    repo: Path,
    *,
    retain_latest: int,
    keep: frozenset[Path] | None = None,
) -> list[str]:
    """Destroy surplus repair worktrees and prune git orphans.

    Args:
        repo: Agent repository root.
        retain_latest: How many recent worktrees to keep beyond ``keep``.
        keep: Worktree paths that must survive retention (for example the
            current run).

    Returns:
        Case ids of destroyed worktrees.
    """
    keep_resolved = {path.resolve() for path in (keep or frozenset()) if path.exists()}
    candidates = list_repair_worktree_dirs(repo)
    optional_slots = max(retain_latest, 0)
    optional_kept: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in keep_resolved:
            continue
        if len(optional_kept) < optional_slots:
            optional_kept.append(path)

    kept = keep_resolved | {path.resolve() for path in optional_kept}
    destroyed: list[str] = []
    for path in candidates:
        if path.resolve() in kept:
            continue
        destroy_repair_worktree(repo, path)
        destroyed.append(path.name)

    prune_orphaned_worktrees(repo)
    if destroyed:
        logger.info(
            "Repair worktree retention removed {} kept={}",
            len(destroyed),
            len(kept),
        )
    return destroyed
