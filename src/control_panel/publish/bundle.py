"""Build publish file bundles."""

from __future__ import annotations

from pathlib import Path

from control_panel.runner.publish import collect_publish_files


def collect_repo_publish_files(repo_dir: Path, migrated: dict[str, Path]) -> dict[str, Path]:
    """Return the final publish file map relative to repository root."""
    if migrated:
        return dict(migrated)
    return collect_publish_files(repo_dir)
