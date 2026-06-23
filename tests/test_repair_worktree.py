"""Tests for repair git worktree helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.worktree import (
    _git_command,
    agent_worktree_parents,
    allocate_repair_case_id,
    build_repair_case_id,
    canonical_worktree_parent,
    ensure_agent_worktrees_parent,
    prune_broken_worktree_slots,
)


def test_git_command_includes_safe_directory() -> None:
    cmd = _git_command(Path("E:/repo/.worktrees/abc"), "diff", "--name-only", "HEAD")
    assert cmd[0] == "git"
    assert cmd[1] == "-c"
    assert cmd[2] == "safe.directory=E:/repo/.worktrees/abc"
    assert cmd[3:] == ["diff", "--name-only", "HEAD"]


def test_agent_worktrees_parent_is_flat(tmp_path: Path) -> None:
    canonical, legacy = agent_worktree_parents(tmp_path)
    assert canonical.name == ".worktrees"
    assert legacy == tmp_path / ".repair" / "worktrees"
    created = ensure_agent_worktrees_parent(tmp_path)
    assert created == canonical
    assert created.is_dir()


def test_build_repair_case_id_format() -> None:
    from datetime import UTC, datetime

    case_id = build_repair_case_id(
        project_label="limbo",
        feature="login_version_1",
        timestamp=datetime(2026, 6, 20, 21, 33, tzinfo=UTC),
    )
    assert case_id == "0620-2133-limbo-login_version_1"


def test_allocate_repair_case_id_avoids_collision(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    when = datetime(2026, 6, 20, 21, 33, tzinfo=UTC)
    parent = ensure_agent_worktrees_parent(tmp_path)
    base = build_repair_case_id(
        project_label="limbo",
        feature="login_version_1",
        timestamp=when,
    )
    (parent / base).mkdir()
    (parent / base / "marker.txt").write_text("occupied", encoding="utf-8")
    allocated = allocate_repair_case_id(
        tmp_path,
        project_label="limbo",
        feature="login_version_1",
        timestamp=when,
    )
    assert allocated == "0620-2133-limbo-login_version_1-2"


def test_allocate_repair_case_id_reuses_empty_orphan_dir(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    when = datetime(2026, 6, 20, 21, 33, tzinfo=UTC)
    parent = ensure_agent_worktrees_parent(tmp_path)
    base = build_repair_case_id(
        project_label="limbo",
        feature="login_version_1",
        timestamp=when,
    )
    (parent / base).mkdir()
    allocated = allocate_repair_case_id(
        tmp_path,
        project_label="limbo",
        feature="login_version_1",
        timestamp=when,
    )
    assert allocated == base


def test_canonical_worktree_parent_honors_custom_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    custom = tmp_path / "external-worktrees"
    monkeypatch.setenv("FIGMA_FLUTTER_WORKTREES_DIR", str(custom))
    repo = tmp_path / "figma-flutter-agent"
    repo.mkdir()
    assert canonical_worktree_parent(repo) == custom.resolve()


def test_prune_broken_worktree_slots_removes_empty_orphan(tmp_path: Path) -> None:
    parent = tmp_path / ".worktrees"
    orphan = parent / "0620-2133-limbo-login_version_1"
    orphan.mkdir(parents=True)
    removed = prune_broken_worktree_slots(tmp_path)
    assert removed == ["0620-2133-limbo-login_version_1"]
    assert not orphan.exists()
