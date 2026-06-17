"""Git worktree lifecycle for compiler repair sandboxes."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import FigmaFlutterError


def _run_git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise FigmaFlutterError(f"git {' '.join(args)} failed: {stderr}")
    return (result.stdout or "").strip()


def create_repair_worktree(agent_repo_root: Path, repair_job_id: str) -> Path:
    """Create a detached worktree for one repair job.

    Args:
        agent_repo_root: figma-flutter-agent repository root (must contain ``.git``).
        repair_job_id: Repair job identifier used in branch name.

    Returns:
        Absolute path to the new worktree directory.

    Raises:
        FigmaFlutterError: When git worktree commands fail.
    """
    repo = agent_repo_root.resolve()
    if not (repo / ".git").exists():
        raise FigmaFlutterError(f"Agent repo is not a git root: {repo}")
    worktrees_parent = repo / ".repair" / "worktrees"
    worktrees_parent.mkdir(parents=True, exist_ok=True)
    branch = f"repair/{repair_job_id}"
    worktree_path = worktrees_parent / repair_job_id
    if worktree_path.exists():
        logger.warning("Repair worktree already exists, reusing {}", worktree_path)
        return worktree_path
    _run_git(repo, "worktree", "add", "-B", branch, str(worktree_path), "HEAD")
    return worktree_path


def destroy_repair_worktree(agent_repo_root: Path, worktree_path: Path) -> None:
    """Remove a repair worktree and its branch metadata.

    Args:
        agent_repo_root: Agent repository root.
        worktree_path: Worktree path previously created for the job.

    Raises:
        FigmaFlutterError: When git cleanup fails.
    """
    repo = agent_repo_root.resolve()
    path = worktree_path.resolve()
    if not path.exists():
        return
    try:
        _run_git(repo, "worktree", "remove", "--force", str(path))
    except FigmaFlutterError:
        logger.exception("git worktree remove failed for {}", path)
        shutil.rmtree(path, ignore_errors=True)
    prune = subprocess.run(
        ["git", "worktree", "prune"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if prune.returncode != 0:
        logger.warning("git worktree prune failed: {}", (prune.stderr or "").strip())


def reset_worktree_hard(worktree_path: Path) -> None:
    """Reset worktree to HEAD and drop untracked files (canonical rollback)."""
    path = worktree_path.resolve()
    _run_git(path, "reset", "--hard", "HEAD")
    _run_git(path, "clean", "-fd")
