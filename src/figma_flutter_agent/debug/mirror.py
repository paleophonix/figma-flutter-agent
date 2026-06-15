"""Deprecated agent-repo mirror helpers (no-op; artifacts live under project ``.debug``)."""

from __future__ import annotations

import re
from pathlib import Path

from figma_flutter_agent.config import agent_repo_root
from figma_flutter_agent.debug.paths import FIGMA_DEBUG_DIR

FIGMA_DEBUG_LOG_DIR = Path("logs/figma-debug")
_SAFE_LABEL_RE = re.compile(r"[^\w.-]+")


def figma_debug_log_root() -> Path:
    """Return legacy ``<agent_repo>/logs/figma-debug`` (migration source only)."""
    return agent_repo_root() / FIGMA_DEBUG_LOG_DIR


def project_mirror_label(project_dir: Path) -> str:
    """Filesystem-safe label for a Flutter project root."""
    from figma_flutter_agent.debug.paths import screen_debug_safe_project

    return screen_debug_safe_project(project_dir)


def figma_debug_mirror_dest(project_dir: Path, artifact: Path) -> Path | None:
    """Map a project ``.debug`` file to its legacy mirror path (migration only)."""
    debug_root = (project_dir.resolve() / FIGMA_DEBUG_DIR).resolve()
    resolved_artifact = artifact.resolve()
    try:
        relative = resolved_artifact.relative_to(debug_root)
    except ValueError:
        return None
    return figma_debug_log_root() / project_mirror_label(project_dir) / relative


def mirror_figma_debug_artifact(project_dir: Path, artifact: Path) -> Path | None:
    """No-op: project artifacts are canonical under ``project_dir/.debug``."""
    _ = (project_dir, artifact)
    return None


def sync_figma_debug_tree(project_dir: Path) -> list[Path]:
    """No-op: full-tree copies to ``logs/figma-debug`` are no longer performed."""
    _ = project_dir
    return []
