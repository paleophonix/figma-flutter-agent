"""Retention and orphan pruning for repair git worktrees."""

from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from figma_flutter_agent.dev.opencode.worktree import (
    destroy_repair_worktree,
    list_repair_worktree_dirs,
    prune_broken_worktree_slots,
    prune_orphaned_worktrees,
    prune_stale_git_worktree_registry,
)


def _worktree_age_minutes(path: Path, *, now: float | None = None) -> float:
    """Return worktree directory age in minutes."""
    reference = now if now is not None else time.time()
    return max(0.0, (reference - path.stat().st_mtime) / 60.0)


def _should_retain_worktree(
    path: Path,
    *,
    keep: frozenset[Path],
    min_age_minutes: int,
    retain_failed: bool,
    retain_stop_reasons: tuple[str, ...],
    outcome_stopped: bool,
    outcome_stop_reason: str | None,
    now: float | None = None,
) -> str | None:
    """Return retention reason when ``path`` must not be destroyed."""
    resolved = path.resolve()
    if resolved in keep:
        return "explicit_keep"
    if min_age_minutes > 0 and _worktree_age_minutes(path, now=now) < min_age_minutes:
        return "min_age"
    if (
        retain_failed
        and outcome_stopped
        and outcome_stop_reason
        and outcome_stop_reason in retain_stop_reasons
        and resolved in keep
    ):
        return "failed_pin"
    return None


def apply_repair_worktree_retention(
    repo: Path,
    *,
    retain_latest: int,
    keep: frozenset[Path] | None = None,
    min_age_minutes: int = 0,
    retain_failed: bool = False,
    retain_stop_reasons: tuple[str, ...] = (),
    outcome_stopped: bool = False,
    outcome_stop_reason: str | None = None,
    now: float | None = None,
) -> list[str]:
    """Destroy surplus repair worktrees and prune git orphans.

    Args:
        repo: Agent repository root.
        retain_latest: How many recent worktrees to keep beyond ``keep``.
        keep: Worktree paths that must survive retention (for example the
            current run).
        min_age_minutes: Skip destruction for worktrees younger than this.
        retain_failed: When true, never destroy explicit ``keep`` paths on
            failed runs whose ``outcome_stop_reason`` is listed.
        retain_stop_reasons: Stop reasons eligible for failed pinning.
        outcome_stopped: Whether the triggering pipeline run stopped early.
        outcome_stop_reason: Orchestrator stop reason for the current run.
        now: Optional epoch seconds override for tests.

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
    retained: list[tuple[str, str]] = []
    for path in candidates:
        if path.resolve() in kept:
            continue
        retain_reason = _should_retain_worktree(
            path,
            keep=keep_resolved,
            min_age_minutes=min_age_minutes,
            retain_failed=retain_failed,
            retain_stop_reasons=retain_stop_reasons,
            outcome_stopped=outcome_stopped,
            outcome_stop_reason=outcome_stop_reason,
            now=now,
        )
        if retain_reason is not None:
            retained.append((path.name, retain_reason))
            continue
        destroy_repair_worktree(repo, path)
        destroyed.append(path.name)

    prune_orphaned_worktrees(repo)
    prune_broken_worktree_slots(repo)
    prune_stale_git_worktree_registry(repo)
    if destroyed or retained:
        logger.info(
            "Repair worktree retention destroyed={} retained={} kept={}",
            len(destroyed),
            len(retained),
            len(kept),
        )
        for name, reason in retained:
            logger.info("Repair worktree retained case={} reason={}", name, reason)
    return destroyed
