"""Reset per-run debug artifacts under ``<agent>/.debug/<feature>/``."""

from __future__ import annotations

import shutil
from pathlib import Path

from figma_flutter_agent.debug.paths import (
    LEGACY_DART_ERRORS_SUBDIR,
    LEGACY_TERMINAL_SUBDIR,
    RUN_LOGS_SUBDIR,
    legacy_project_debug_root,
    legacy_project_run_log_path,
    legacy_project_run_logs_dir,
    project_run_log_path,
)


def reset_pipeline_run_debug_dirs(project_dir: Path, feature_name: str | None = None) -> None:
    """Clear per-screen ``last.log`` and remove deprecated per-run log folders.

    Args:
        project_dir: Flutter project root.
        feature_name: Active screen slug whose ``last.log`` should be truncated.
    """
    legacy_debug_root = legacy_project_debug_root(project_dir)
    if feature_name:
        run_log = project_run_log_path(project_dir, feature_name)
        if run_log.is_file():
            run_log.unlink()
    legacy_run_log = legacy_project_run_log_path(project_dir)
    if legacy_run_log.is_file():
        legacy_run_log.unlink()
    for subdir in (RUN_LOGS_SUBDIR, LEGACY_TERMINAL_SUBDIR, LEGACY_DART_ERRORS_SUBDIR):
        target = legacy_debug_root / subdir
        if not target.exists():
            target = legacy_project_run_logs_dir(project_dir) if subdir == RUN_LOGS_SUBDIR else target
        if not target.exists():
            continue
        if target.is_file():
            target.unlink()
            continue
        shutil.rmtree(target, ignore_errors=True)
