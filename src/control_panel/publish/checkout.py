"""Local git checkout helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

from figma_flutter_agent.errors import FigmaFlutterError


def repo_cache_dir(cache_root: Path, repo_key: str) -> Path:
    """Return the on-disk cache directory for a repository."""
    return cache_root.expanduser().resolve() / repo_key


def authenticated_git_remote_url(*, remote_url: str, token: str) -> str:
    """Inject HTTPS credentials for non-interactive git clone/fetch.

    Args:
        remote_url: Remote repository URL.
        token: Provider personal access token.

    Returns:
        Remote URL with embedded credentials when ``token`` is non-empty.
    """
    cleaned = token.strip()
    if not cleaned:
        return remote_url
    parsed = urlparse(remote_url)
    if parsed.scheme not in {"http", "https"}:
        return remote_url
    netloc = parsed.netloc.rsplit("@", maxsplit=1)[-1]
    username = "oauth2" if "gitlab" in netloc else "x-access-token"
    auth_netloc = f"{username}:{quote(cleaned, safe='')}@{netloc}"
    return urlunparse(parsed._replace(netloc=auth_netloc))


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return env


def _is_valid_git_checkout(cache_dir: Path) -> bool:
    git_dir = cache_dir / ".git"
    if not git_dir.exists():
        return False
    result = subprocess.run(
        ["git", "-C", cache_dir.as_posix(), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    return result.returncode == 0


def _reset_cache_dir(cache_dir: Path) -> None:
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)


def ensure_shallow_clone(
    *,
    remote_url: str,
    cache_dir: Path,
    branch: str,
    git_token: str = "",
) -> Path:
    """Clone or fetch a shallow repository checkout."""
    cache_dir = cache_dir.expanduser().resolve()
    auth_remote = authenticated_git_remote_url(remote_url=remote_url, token=git_token)
    env = _git_env()
    if cache_dir.exists() and not _is_valid_git_checkout(cache_dir):
        _reset_cache_dir(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    git_dir = cache_dir / ".git"
    if git_dir.exists():
        fetch = subprocess.run(
            ["git", "-C", cache_dir.as_posix(), "fetch", "origin", branch, "--depth", "1"],
            capture_output=True,
            text=True,
            env=env,
        )
        if fetch.returncode != 0:
            _reset_cache_dir(cache_dir)
        else:
            checkout = subprocess.run(
                ["git", "-C", cache_dir.as_posix(), "checkout", branch],
                capture_output=True,
                text=True,
                env=env,
            )
            if checkout.returncode == 0:
                return cache_dir
            _reset_cache_dir(cache_dir)
    result = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            branch,
            auth_remote,
            cache_dir.as_posix(),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise FigmaFlutterError(f"Git clone failed: {detail}")
    return cache_dir
