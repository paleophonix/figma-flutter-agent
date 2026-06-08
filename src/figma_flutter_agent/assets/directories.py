"""Flutter asset directory helpers."""

from __future__ import annotations

from pathlib import Path


def ensure_asset_directories(project_dir: Path) -> tuple[Path, Path, Path]:
    """Create and return icons/images/illustrations asset directories."""
    icons_dir = project_dir / "assets" / "icons"
    images_dir = project_dir / "assets" / "images"
    illustrations_dir = project_dir / "assets" / "illustrations"
    icons_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    illustrations_dir.mkdir(parents=True, exist_ok=True)
    return icons_dir, images_dir, illustrations_dir
