"""Collect Flutter project files for GitLab commits."""

from __future__ import annotations

from pathlib import Path


def collect_publish_files(project_dir: Path) -> dict[str, Path]:
    """Return relative project files suitable for GitLab commits."""
    files: dict[str, Path] = {}
    candidates = [
        project_dir / "pubspec.yaml",
        project_dir / "pubspec.lock",
    ]
    for folder in ("lib", "assets"):
        root = project_dir / folder
        if root.is_dir():
            candidates.extend(path for path in root.rglob("*") if path.is_file())
    for path in candidates:
        if path.is_file():
            files[path.relative_to(project_dir).as_posix()] = path
    return files
