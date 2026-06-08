"""Manifest helpers for Figma import workflows."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.batch.manifest import (
    BatchManifest,
    ScreenEntry,
    load_batch_manifest,
    write_batch_manifest,
)
from figma_flutter_agent.generator.layout.common import to_snake_case


def _unique_feature_name(feature: str, manifest: BatchManifest, node_id: str) -> str:
    """Return a manifest feature slug, preserving the name for the same node id."""
    for screen in manifest.screens:
        if screen.node_id == node_id:
            return screen.feature
    base = feature or f"screen_{node_id.replace(':', '_')}"
    if not any(screen.feature == base for screen in manifest.screens):
        return base
    suffix = 2
    while any(screen.feature == f"{base}_{suffix}" for screen in manifest.screens):
        suffix += 1
    return f"{base}_{suffix}"


def resolve_import_feature_name(
    user_slug: str | None,
    figma_frame_name: str,
    manifest: BatchManifest,
    node_id: str,
) -> str:
    """Resolve a unique ``screens.yaml`` feature slug for a frame import."""
    raw = (user_slug or "").strip()
    provisional = to_snake_case(raw) if raw else to_snake_case(figma_frame_name)
    return _unique_feature_name(provisional, manifest, node_id)


def upsert_screen_in_manifest(
    manifest_path: Path,
    *,
    project_dir: Path,
    file_key: str,
    screen: ScreenEntry,
) -> BatchManifest:
    """Insert or replace one screen entry in ``screens.yaml``."""
    if manifest_path.is_file():
        manifest = load_batch_manifest(manifest_path)
        screens = [item for item in manifest.screens if item.node_id != screen.node_id]
        screens.append(screen)
        updated = BatchManifest(
            file_key=file_key,
            project_dir=project_dir,
            screens=tuple(screens),
            figma_file_url=manifest.figma_file_url,
        )
    else:
        updated = BatchManifest(
            file_key=file_key,
            project_dir=project_dir,
            screens=(screen,),
        )
    write_batch_manifest(manifest_path, updated)
    logger.info(
        "Upserted screen {} ({}) in {}",
        screen.feature,
        screen.node_id,
        manifest_path.as_posix(),
    )
    return updated


def find_manifest_screen_for_frame(
    manifest: BatchManifest,
    *,
    file_key: str,
    node_id: str,
) -> ScreenEntry | None:
    """Return the manifest screen entry matching a frame URL, if present."""
    if manifest.file_key != file_key:
        return None
    for screen in manifest.screens:
        if screen.node_id == node_id:
            return screen
    return None
