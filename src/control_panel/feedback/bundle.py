"""Collect screen, asset, and debug files for feedback artifact bundles."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.generator.paths import screen_file_path


def collect_screen_and_asset_files(
    *,
    project_dir: Path,
    feature_slug: str,
) -> dict[str, Path]:
    """Return sandbox files for one screen and its assets (repo-relative keys)."""
    files: dict[str, Path] = {}
    lib_root = project_dir / "lib"
    if lib_root.is_dir():
        for path in lib_root.rglob("*.dart"):
            if not path.is_file():
                continue
            rel = path.relative_to(project_dir).as_posix()
            if feature_slug in rel or path.name.endswith("_screen.dart"):
                files[rel] = path
    assets_root = project_dir / "assets"
    if assets_root.is_dir():
        for path in assets_root.rglob("*"):
            if path.is_file():
                files[path.relative_to(project_dir).as_posix()] = path
    screen_rel = screen_file_path(feature_slug, architecture="feature_first")
    screen_abs = project_dir / screen_rel
    if screen_abs.is_file():
        files[screen_rel.replace("\\", "/")] = screen_abs
    return files


def build_feedback_bundle_zip(
    *,
    project_dir: Path,
    feature_slug: str,
    job_id: str,
    debug_zip_path: Path | None = None,
) -> Path:
    """Create a zip with project screen/assets and optional debug archive."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="control-panel-feedback-bundle-"))
    zip_path = tmp_dir / f"{job_id}-feedback.zip"
    project_files = collect_screen_and_asset_files(
        project_dir=project_dir,
        feature_slug=feature_slug,
    )
    debug_root = screen_root(project_dir, feature_slug)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel, path in sorted(project_files.items()):
            archive.write(path, arcname=f"project/{rel}")
        if debug_root.is_dir():
            for path in sorted(debug_root.rglob("*")):
                if path.is_file():
                    archive.write(
                        path,
                        arcname=f"debug/{path.relative_to(debug_root).as_posix()}",
                    )
        if debug_zip_path is not None and debug_zip_path.is_file():
            archive.write(debug_zip_path, arcname="debug-bundle.zip")
    return zip_path
