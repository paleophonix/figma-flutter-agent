"""Mirror Flutter project ``.figma_debug`` artifacts into the agent ``logs/`` tree."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import agent_repo_root
from figma_flutter_agent.debug.paths import FIGMA_DEBUG_DIR

FIGMA_DEBUG_LOG_DIR = Path("logs/figma-debug")
_SAFE_LABEL_RE = re.compile(r"[^\w.-]+")


def figma_debug_log_root() -> Path:
    """Return ``<agent_repo>/logs/figma-debug``."""
    return agent_repo_root() / FIGMA_DEBUG_LOG_DIR


def project_mirror_label(project_dir: Path) -> str:
    """Filesystem-safe label for a Flutter project root."""
    resolved = project_dir.resolve()
    parts = resolved.parts[-2:] if len(resolved.parts) >= 2 else resolved.parts[-1:]
    label = "_".join(_SAFE_LABEL_RE.sub("_", part).strip("_") for part in parts if part)
    return label or "project"


def figma_debug_mirror_dest(project_dir: Path, artifact: Path) -> Path | None:
    """Map a project ``.figma_debug`` file to its mirror path under ``logs/figma-debug``."""
    debug_root = (project_dir.resolve() / FIGMA_DEBUG_DIR).resolve()
    resolved_artifact = artifact.resolve()
    try:
        relative = resolved_artifact.relative_to(debug_root)
    except ValueError:
        return None
    return figma_debug_log_root() / project_mirror_label(project_dir) / relative


def mirror_figma_debug_artifact(project_dir: Path, artifact: Path) -> Path | None:
    """Copy one ``.figma_debug`` file into ``logs/figma-debug/<project>/…``.

    Args:
        project_dir: Flutter project root containing ``.figma_debug``.
        artifact: File path under that debug tree.

    Returns:
        Destination path when mirrored, else ``None``.
    """
    if not artifact.is_file():
        return None
    dest = figma_debug_mirror_dest(project_dir, artifact)
    if dest is None:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact, dest)
    logger.debug("Mirrored figma_debug artifact to {}", dest.as_posix())
    return dest


def sync_figma_debug_tree(project_dir: Path) -> list[Path]:
    """Copy the full ``.figma_debug`` directory into ``logs/figma-debug/<project>/``.

    Args:
        project_dir: Flutter project root.

    Returns:
        Paths of files copied (empty when the source tree is missing).
    """
    source_root = project_dir.resolve() / FIGMA_DEBUG_DIR
    if not source_root.is_dir():
        return []
    dest_root = figma_debug_log_root() / project_mirror_label(project_dir)
    copied: list[Path] = []
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root)
        dest = dest_root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        copied.append(dest)
    if copied:
        logger.info(
            "Synced {} figma_debug file(s) to {}",
            len(copied),
            dest_root.as_posix(),
        )
    return copied
