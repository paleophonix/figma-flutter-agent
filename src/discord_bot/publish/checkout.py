"""Local git checkout helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from figma_flutter_agent.errors import FigmaFlutterError


def repo_cache_dir(cache_root: Path, repo_key: str) -> Path:
    """Return the on-disk cache directory for a repository."""
    return cache_root.expanduser().resolve() / repo_key


def ensure_shallow_clone(
    *,
    remote_url: str,
    cache_dir: Path,
    branch: str,
) -> Path:
    """Clone or fetch a shallow repository checkout."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    git_dir = cache_dir / ".git"
    if git_dir.exists():
        subprocess.run(
            ["git", "-C", cache_dir.as_posix(), "fetch", "origin", branch, "--depth", "1"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", cache_dir.as_posix(), "checkout", branch],
            check=True,
            capture_output=True,
            text=True,
        )
        return cache_dir
    result = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            branch,
            remote_url,
            cache_dir.as_posix(),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FigmaFlutterError(f"Git clone failed: {result.stderr.strip()}")
    return cache_dir
