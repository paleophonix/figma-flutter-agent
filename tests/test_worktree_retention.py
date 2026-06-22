"""Tests for repair worktree retention."""

from __future__ import annotations

import os
import time
from pathlib import Path

from figma_flutter_agent.dev.opencode.worktree import list_repair_worktree_dirs
from figma_flutter_agent.dev.opencode.worktree_retention import apply_repair_worktree_retention


def test_apply_repair_worktree_retention_keeps_latest_and_explicit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    parent = tmp_path / ".worktrees"
    parent.mkdir(parents=True)
    keep = parent / "keep_me"
    old = parent / "old_one"
    mid = parent / "mid_one"
    for path in (keep, old, mid):
        path.mkdir()
    now = time.time()
    os.utime(keep, (now - 5, now - 5))
    os.utime(mid, (now - 1, now - 1))
    os.utime(old, (now - 20, now - 20))

    destroyed: list[Path] = []

    def _fake_destroy(_repo: Path, path: Path) -> None:
        destroyed.append(path)

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.worktree_retention.destroy_repair_worktree",
        _fake_destroy,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.worktree_retention.prune_orphaned_worktrees",
        lambda _repo: None,
    )

    removed = apply_repair_worktree_retention(
        tmp_path,
        retain_latest=1,
        keep=frozenset({keep}),
    )
    assert "keep_me" not in removed
    assert "mid_one" not in removed
    assert removed == ["old_one"]


def test_apply_repair_worktree_retention_skips_fresh_worktrees(
    tmp_path: Path,
    monkeypatch,
) -> None:
    parent = tmp_path / ".worktrees"
    parent.mkdir(parents=True)
    fresh = parent / "fresh_case"
    old = parent / "old_case"
    fresh.mkdir()
    old.mkdir()
    now = time.time()
    os.utime(fresh, (now, now))
    os.utime(old, (now - 3600, now - 3600))

    destroyed: list[str] = []

    def _fake_destroy(_repo: Path, path: Path) -> None:
        destroyed.append(path.name)

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.worktree_retention.destroy_repair_worktree",
        _fake_destroy,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.worktree_retention.prune_orphaned_worktrees",
        lambda _repo: None,
    )

    removed = apply_repair_worktree_retention(
        tmp_path,
        retain_latest=0,
        keep=frozenset(),
        min_age_minutes=30,
    )
    assert "fresh_case" not in removed
    assert removed == ["old_case"]


def test_list_repair_worktree_dirs_newest_first(tmp_path: Path) -> None:
    parent = tmp_path / ".worktrees"
    parent.mkdir(parents=True)
    first = parent / "aaa"
    second = parent / "bbb"
    first.mkdir()
    second.mkdir()
    now = time.time()
    os.utime(first, (now - 10, now - 10))
    os.utime(second, (now, now))
    ordered = list_repair_worktree_dirs(tmp_path)
    assert [path.name for path in ordered] == ["bbb", "aaa"]


def test_list_repair_worktree_dirs_reads_legacy_parent(tmp_path: Path) -> None:
    legacy = tmp_path / ".repair" / "worktrees" / "legacy_case"
    legacy.mkdir(parents=True)
    ordered = list_repair_worktree_dirs(tmp_path)
    assert [path.name for path in ordered] == ["legacy_case"]
