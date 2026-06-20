"""Tests for repair git worktree helpers."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.dev.opencode.worktree import _git_command


def test_git_command_includes_safe_directory() -> None:
    cmd = _git_command(Path("E:/repo/.repair/worktrees/abc"), "diff", "--name-only", "HEAD")
    assert cmd[0] == "git"
    assert cmd[1] == "-c"
    assert cmd[2] == "safe.directory=E:/repo/.repair/worktrees/abc"
    assert cmd[3:] == ["diff", "--name-only", "HEAD"]
