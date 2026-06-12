"""Legacy agent-repo ``logs/`` debug trees (migration sources only)."""

from __future__ import annotations

import shutil

from loguru import logger

from figma_flutter_agent.config import agent_repo_root

# Deprecated mirror shards under ``<agent_repo>/logs/`` (never write on new runs).
LEGACY_AGENT_LOG_DEBUG_DIRS = (
    "figma-debug",
    "dart",
    "reports",
    "semantics",
    "dart-errors",
)


def purge_legacy_agent_debug_log_dirs() -> int:
    """Delete deprecated debug mirror folders under the agent ``logs/`` directory.

    Pipeline artifacts belong under ``<project_dir>/.debug/`` only. Global telemetry
    stays in ``logs/figma_flutter_agent.log``.

    Returns:
        Number of top-level legacy directories removed.
    """
    logs_root = agent_repo_root() / "logs"
    removed = 0
    for name in LEGACY_AGENT_LOG_DEBUG_DIRS:
        target = logs_root / name
        if not target.exists():
            continue
        if target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target, ignore_errors=True)
        removed += 1
        logger.debug("Removed legacy agent log directory {}", target.as_posix())
    return removed
