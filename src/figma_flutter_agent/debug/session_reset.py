"""Reset per-run debug artifacts under ``<project>/.debug``."""

from __future__ import annotations

import shutil
from pathlib import Path

from figma_flutter_agent.debug.paths import (
    FIGMA_DEBUG_DIR,
    LEGACY_DART_ERRORS_SUBDIR,
    LEGACY_TERMINAL_SUBDIR,
    RUN_LOGS_SUBDIR,
)


def reset_pipeline_run_debug_dirs(project_dir: Path) -> None:
    """Clear ``.debug/logs`` and remove deprecated per-run log folders.

    Args:
        project_dir: Flutter project root.
    """
    debug_root = project_dir / FIGMA_DEBUG_DIR
    for subdir in (RUN_LOGS_SUBDIR, LEGACY_TERMINAL_SUBDIR, LEGACY_DART_ERRORS_SUBDIR):
        target = debug_root / subdir
        if not target.exists():
            continue
        if target.is_file():
            target.unlink()
            continue
        shutil.rmtree(target, ignore_errors=True)
