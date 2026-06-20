"""Git worktree lifecycle for compiler repair sandboxes."""

from __future__ import annotations

import re
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import FigmaFlutterError

AGENT_WORKTREES_DIRNAME = ".worktrees"
LEGACY_AGENT_WORKTREES_REL = Path(".repair") / "worktrees"
_WORKTREE_TOKEN_RE = re.compile(r"[^\w.-]+")
_MAX_WORKTREE_DIRNAME_LEN = 120


def _sanitize_worktree_token(value: str) -> str:
    """Normalize a path segment for git worktree directory names."""
    return _WORKTREE_TOKEN_RE.sub("-", value).strip("-") or ""


def build_repair_case_id(
    *,
    project_label: str,
    feature: str,
    timestamp: datetime | None = None,
    disambiguator: str | None = None,
) -> str:
    """Build a human-readable worktree directory name.

    Format: ``MMDD-HHMM-<project>-<screen>`` (optional ``-`` suffix on collision).

    Example: ``0620-2133-limbo-login_version_1``.

    Args:
        project_label: Sanitized Flutter project folder label (e.g. ``limbo``).
        feature: Screen feature slug.
        timestamp: Optional UTC timestamp for deterministic tests.
        disambiguator: Optional suffix when the base name already exists.

    Returns:
        Directory name safe for git worktree paths on Windows.
    """
    when = timestamp or datetime.now(tz=UTC)
    stamp = when.strftime("%m%d-%H%M")
    project = _sanitize_worktree_token(project_label) or "project"
    screen = _sanitize_worktree_token(feature) or "screen"
    parts = [stamp, project, screen]
    if disambiguator:
        parts.append(disambiguator)
    case_id = "-".join(parts)
    if len(case_id) <= _MAX_WORKTREE_DIRNAME_LEN:
        return case_id
    overhead = len(f"{stamp}-{project}-")
    if disambiguator:
        overhead += len(disambiguator) + 1
    trimmed_screen = screen[: max(_MAX_WORKTREE_DIRNAME_LEN - overhead, 8)].rstrip("-") or "screen"
    parts = [stamp, project, trimmed_screen]
    if disambiguator:
        parts.append(disambiguator)
    return "-".join(parts)


def allocate_repair_case_id(
    repo: Path,
    *,
    project_label: str,
    feature: str,
    timestamp: datetime | None = None,
) -> str:
    """Return a unique ``MMDD-HHMM-project-screen`` worktree directory name.

    Args:
        repo: Agent git repository root.
        project_label: Sanitized Flutter project folder label.
        feature: Screen feature slug.
        timestamp: Optional UTC timestamp for deterministic tests.

    Returns:
        Unused directory name under ``<repo>/.worktrees/``.
    """
    parent = ensure_agent_worktrees_parent(repo)
    base = build_repair_case_id(
        project_label=project_label,
        feature=feature,
        timestamp=timestamp,
    )
    if not (parent / base).exists():
        return base
    for index in range(2, 100):
        candidate = build_repair_case_id(
            project_label=project_label,
            feature=feature,
            timestamp=timestamp,
            disambiguator=str(index),
        )
        if not (parent / candidate).exists():
            return candidate
    fallback = build_repair_case_id(
        project_label=project_label,
        feature=feature,
        timestamp=timestamp,
        disambiguator=uuid.uuid4().hex[:4],
    )
    return fallback


def agent_worktree_parents(repo: Path) -> tuple[Path, Path]:
    """Return canonical and legacy agent-repo worktree container paths."""
    root = repo.resolve()
    return root / AGENT_WORKTREES_DIRNAME, root / LEGACY_AGENT_WORKTREES_REL


def ensure_agent_worktrees_parent(repo: Path) -> Path:
    """Create and return ``<repo>/.worktrees``."""
    parent = agent_worktree_parents(repo)[0]
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def existing_worktree_parents(repo: Path) -> list[Path]:
    """Return worktree container directories that exist (canonical first)."""
    return [path for path in agent_worktree_parents(repo) if path.is_dir()]


def list_repair_worktree_dirs(repo: Path) -> list[Path]:
    """List repair worktree directories from canonical and legacy roots."""
    seen: set[str] = set()
    dirs: list[Path] = []
    for parent in existing_worktree_parents(repo):
        for path in parent.iterdir():
            if not path.is_dir() or path.name in seen:
                continue
            seen.add(path.name)
            dirs.append(path)
    dirs.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return dirs


def resolve_repair_worktree_path(repo: Path, case_id: str) -> Path | None:
    """Return an on-disk repair worktree path for ``case_id``, if present."""
    for parent in existing_worktree_parents(repo):
        candidate = parent / case_id
        if candidate.is_dir():
            return candidate
    return None


def _safe_directory_flag(repo: Path) -> str:
    """Return ``-c safe.directory=…`` value for Windows worktrees on FAT/exFAT."""
    return f"safe.directory={repo.resolve().as_posix()}"


def _git_command(repo: Path, *args: str) -> list[str]:
    """Build a git argv with per-invocation ``safe.directory`` (no global config)."""
    return ["git", "-c", _safe_directory_flag(repo), *args]


def _run_git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    result = subprocess.run(
        _git_command(repo, *args),
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise FigmaFlutterError(f"git {' '.join(args)} failed: {stderr}")
    return (result.stdout or "").strip()


def _is_usable_git_worktree(worktree_path: Path) -> bool:
    """Return True when ``worktree_path`` is a usable git worktree."""
    if not (worktree_path / ".git").exists():
        return False
    result = subprocess.run(
        _git_command(worktree_path, "rev-parse", "--is-inside-work-tree"),
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and (result.stdout or "").strip() == "true"


def create_repair_worktree(agent_repo_root: Path, repair_job_id: str) -> Path:
    """Create a detached worktree for one repair job under ``<repo>/.worktrees``."""
    repo = agent_repo_root.resolve()
    if not (repo / ".git").exists():
        raise FigmaFlutterError(f"Agent repo is not a git root: {repo}")
    branch = f"repair/{repair_job_id}"
    for parent in existing_worktree_parents(repo):
        existing = parent / repair_job_id
        if existing.exists() and _is_usable_git_worktree(existing):
            logger.warning("Repair worktree already exists, reusing {}", existing)
            return existing
    worktrees_parent = ensure_agent_worktrees_parent(repo)
    worktree_path = worktrees_parent / repair_job_id
    if worktree_path.exists():
        if _is_usable_git_worktree(worktree_path):
            logger.warning("Repair worktree already exists, reusing {}", worktree_path)
            return worktree_path
        logger.warning("Stale repair worktree at {}; recreating", worktree_path)
        destroy_repair_worktree(repo, worktree_path)
    _run_git(repo, "worktree", "add", "-B", branch, str(worktree_path), "HEAD")
    return worktree_path


def destroy_repair_worktree(agent_repo_root: Path, worktree_path: Path) -> None:
    """Remove a repair worktree and its branch metadata."""
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
        _git_command(repo, "worktree", "prune"),
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if prune.returncode != 0:
        logger.warning("git worktree prune failed: {}", (prune.stderr or "").strip())


def reset_worktree_hard(worktree_path: Path) -> None:
    """Reset worktree to HEAD and drop untracked files."""
    path = worktree_path.resolve()
    _run_git(path, "reset", "--hard", "HEAD")
    _run_git(path, "clean", "-fd")


def prune_orphaned_worktrees(repo: Path) -> None:
    """Drop git worktree metadata for deleted repair directories."""
    resolved = repo.resolve()
    result = subprocess.run(
        _git_command(resolved, "worktree", "prune"),
        cwd=resolved,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning(
            "git worktree prune failed: {}",
            (result.stderr or result.stdout or "").strip(),
        )
