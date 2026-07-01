"""Git worktree lifecycle for compiler repair sandboxes."""

from __future__ import annotations

import os
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
    if not _directory_occupies_worktree_slot(parent / base):
        return base
    for index in range(2, 100):
        candidate = build_repair_case_id(
            project_label=project_label,
            feature=feature,
            timestamp=timestamp,
            disambiguator=str(index),
        )
        if not _directory_occupies_worktree_slot(parent / candidate):
            return candidate
    fallback = build_repair_case_id(
        project_label=project_label,
        feature=feature,
        timestamp=timestamp,
        disambiguator=uuid.uuid4().hex[:4],
    )
    return fallback


def canonical_worktree_parent(repo: Path) -> Path:
    """Return the primary repair worktree container for ``repo``."""
    root = repo.resolve()
    custom = os.environ.get("FIGMA_FLUTTER_WORKTREES_DIR", "").strip()
    if custom:
        return Path(custom).expanduser().resolve()
    return root / AGENT_WORKTREES_DIRNAME


def worktree_parent_candidates(repo: Path) -> list[Path]:
    """Return canonical and legacy worktree container paths (deduped)."""
    root = repo.resolve()
    seen: set[str] = set()
    candidates: list[Path] = []
    for path in (
        canonical_worktree_parent(root),
        root / AGENT_WORKTREES_DIRNAME,
        root / LEGACY_AGENT_WORKTREES_REL,
    ):
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(path)
    return candidates


def agent_worktree_parents(repo: Path) -> tuple[Path, Path]:
    """Return canonical and legacy agent-repo worktree container paths."""
    root = repo.resolve()
    return canonical_worktree_parent(root), root / LEGACY_AGENT_WORKTREES_REL


def ensure_agent_worktrees_parent(repo: Path) -> Path:
    """Create and return the canonical repair worktree container."""
    parent = canonical_worktree_parent(repo)
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def existing_worktree_parents(repo: Path) -> list[Path]:
    """Return worktree container directories that exist (canonical first)."""
    existing = [path for path in worktree_parent_candidates(repo) if path.is_dir()]
    if existing:
        return existing
    return [canonical_worktree_parent(repo)]


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


def _directory_occupies_worktree_slot(path: Path) -> bool:
    """Return True when a path blocks reuse of a repair worktree directory name."""
    if not path.is_dir():
        return False
    if _is_usable_git_worktree(path):
        return True
    try:
        return any(path.iterdir())
    except OSError:
        return True


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
        if worktree_path.exists():
            raise FigmaFlutterError(
                f"Stale repair worktree directory is locked and could not be removed: {worktree_path}"
            )
    _run_git(repo, "worktree", "add", "-B", branch, str(worktree_path), "HEAD")
    return worktree_path


def destroy_repair_worktree(agent_repo_root: Path, worktree_path: Path) -> None:
    """Remove a repair worktree, drop its local branch, and prune git metadata."""
    repo = agent_repo_root.resolve()
    path = worktree_path.resolve()
    case_id = path.name
    branch = f"repair/{case_id}"
    if not path.exists():
        _delete_repair_branch(repo, branch)
        return
    if _is_usable_git_worktree(path):
        try:
            _run_git(repo, "worktree", "remove", "--force", str(path))
        except FigmaFlutterError:
            logger.exception("git worktree remove failed for {}", path)
            shutil.rmtree(path, ignore_errors=True)
    else:
        shutil.rmtree(path, ignore_errors=True)
    _delete_repair_branch(repo, branch)
    prune = subprocess.run(
        _git_command(repo, "worktree", "prune"),
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if prune.returncode != 0:
        logger.warning("git worktree prune failed: {}", (prune.stderr or "").strip())
    prune_stale_git_worktree_registry(repo)


def _delete_repair_branch(repo: Path, branch: str) -> None:
    """Delete a local ``repair/*`` branch when it is not checked out."""
    result = subprocess.run(
        _git_command(repo, "branch", "-D", branch),
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        if stderr and "not found" not in stderr.lower():
            logger.warning("git branch -D {} failed: {}", branch, stderr)


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


def _worktree_path_from_meta_dir(meta_dir: Path) -> Path | None:
    """Resolve checkout root from one ``.git/worktrees/<id>/`` admin directory."""
    gitdir_file = meta_dir / "gitdir"
    try:
        if not gitdir_file.is_file():
            return None
        linked_git = Path(gitdir_file.read_text(encoding="utf-8").strip())
    except OSError:
        return None
    if linked_git.name != ".git":
        return None
    return linked_git.parent


def _worktree_meta_is_stale(meta_dir: Path, worktree_path: Path | None) -> bool:
    """Return whether git worktree admin metadata can be dropped."""
    if worktree_path is None:
        return True
    try:
        return not worktree_path.exists()
    except OSError:
        return True


def prune_stale_git_worktree_registry(repo: Path) -> list[str]:
    """Remove ``.git/worktrees/*`` entries whose checkout directory is gone."""
    meta_root = repo.resolve() / ".git" / "worktrees"
    if not meta_root.is_dir():
        return []
    removed: list[str] = []
    for meta_dir in list(meta_root.iterdir()):
        if not meta_dir.is_dir():
            continue
        worktree_path = _worktree_path_from_meta_dir(meta_dir)
        if not _worktree_meta_is_stale(meta_dir, worktree_path):
            continue
        logger.info("Pruning stale git worktree registry {}", meta_dir.name)
        shutil.rmtree(meta_dir, ignore_errors=True)
        if not meta_dir.exists():
            removed.append(meta_dir.name)
    if removed:
        prune_orphaned_worktrees(repo)
    return removed


def prune_broken_worktree_slots(repo: Path) -> list[str]:
    """Remove empty or non-git repair directories left after failed destroys."""
    removed: list[str] = []
    for parent in worktree_parent_candidates(repo):
        if not parent.is_dir():
            continue
        for path in list(parent.iterdir()):
            if not path.is_dir() or _is_usable_git_worktree(path):
                continue
            logger.info("Pruning broken repair worktree slot {}", path)
            destroy_repair_worktree(repo, path)
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
            if not path.exists():
                removed.append(path.name)
    prune_orphaned_worktrees(repo)
    prune_stale_git_worktree_registry(repo)
    return removed


def list_local_repair_branches(repo: Path) -> list[str]:
    """Return sorted local branch names under ``repair/*``."""
    resolved = repo.resolve()
    if not (resolved / ".git").exists():
        return []
    result = subprocess.run(
        _git_command(resolved, "for-each-ref", "--format=%(refname:short)", "refs/heads/repair/"),
        cwd=resolved,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    branches: list[str] = []
    for line in (result.stdout or "").splitlines():
        name = line.strip().lstrip("*").strip()
        if name.startswith("repair/"):
            branches.append(name)
    return sorted(branches)


def collect_repair_git_leaks(repo: Path) -> tuple[list[str], list[str]]:
    """Snapshot repair worktree directory names and local ``repair/*`` branches."""
    worktrees = sorted(path.name for path in list_repair_worktree_dirs(repo))
    branches = list_local_repair_branches(repo)
    return worktrees, branches


def purge_repair_git_leaks(repo: Path) -> tuple[list[str], list[str]]:
    """Remove every repair worktree checkout and local ``repair/*`` branch under ``repo``.

    Args:
        repo: Agent git repository root.

    Returns:
        Tuple of removed worktree directory names and removed branch names.
    """
    resolved = repo.resolve()
    if not (resolved / ".git").exists():
        return [], []

    removed_dirs: list[str] = []
    for path in list(list_repair_worktree_dirs(resolved)):
        case_id = path.name
        destroy_repair_worktree(resolved, path)
        removed_dirs.append(case_id)

    removed_branches: list[str] = []
    for branch in list_local_repair_branches(resolved):
        _delete_repair_branch(resolved, branch)
        removed_branches.append(branch)

    prune_orphaned_worktrees(resolved)
    prune_broken_worktree_slots(resolved)
    prune_stale_git_worktree_registry(resolved)
    return removed_dirs, removed_branches
