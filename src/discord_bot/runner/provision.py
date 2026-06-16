"""Provision per-user Flutter projects from the agent skeleton template."""

from __future__ import annotations

import shutil
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.pipeline.helpers import validate_project_dir


def flutter_skeleton_dir() -> Path:
    """Return the canonical Flutter skeleton fixture path."""
    return agent_repo_root() / "tests" / "fixtures" / "flutter_skeleton"


def copy_skeleton_project(target_dir: Path) -> None:
    """Copy the Flutter skeleton without stale tool artifacts."""
    skeleton = flutter_skeleton_dir()
    if not skeleton.is_dir():
        msg = f"Flutter skeleton not found: {skeleton}"
        raise FileNotFoundError(msg)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(
        skeleton,
        target_dir,
        ignore=shutil.ignore_patterns(".dart_tool", "build"),
    )
    logger.info("Provisioned Flutter skeleton at {}", target_dir.as_posix())


def ensure_user_project(project_dir: Path) -> Path:
    """Ensure a Flutter project exists at ``project_dir``.

    Args:
        project_dir: Desired per-user project root.

    Returns:
        Resolved project directory.
    """
    resolved = project_dir.expanduser().resolve()
    if (resolved / "pubspec.yaml").is_file():
        validate_project_dir(resolved)
        return resolved
    resolved.parent.mkdir(parents=True, exist_ok=True)
    copy_skeleton_project(resolved)
    validate_project_dir(resolved)
    return resolved
