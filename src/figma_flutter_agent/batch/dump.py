"""Minimal Figma API dumps (one Tier-1 request per screen)."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry, default_dump_path
from figma_flutter_agent.figma.client import FigmaConnector


async def dump_screen_node(
    connector: FigmaConnector,
    *,
    file_key: str,
    screen: ScreenEntry,
    project_dir: Path,
) -> Path:
    """Fetch one frame subtree and write ``.debug/raw/<feature>_layout.json``.

    Uses a single ``GET /files/:key/nodes`` call (Tier 1).

    Args:
        connector: Active Figma connector.
        file_key: Figma file key.
        screen: Screen manifest entry.
        project_dir: Flutter project root for debug output.

    Returns:
        Path to the written dump file.
    """
    target = screen.dump or default_dump_path(project_dir, screen.feature)
    target.parent.mkdir(parents=True, exist_ok=True)
    response = await connector.fetch_nodes(file_key, [screen.node_id])
    entry = response.nodes.get(screen.node_id)
    if entry is None or entry.document is None:
        msg = f"Node {screen.node_id} was not found in Figma file {file_key}"
        raise ValueError(msg)
    target.write_text(json.dumps(entry.document, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote dump for {} to {}", screen.feature, target.as_posix())
    return target


async def dump_manifest_screens(
    connector: FigmaConnector,
    manifest: BatchManifest,
    *,
    skip_existing: bool = True,
) -> list[tuple[ScreenEntry, Path]]:
    """Dump all screens in ``manifest``, optionally skipping existing files."""
    written: list[tuple[ScreenEntry, Path]] = []
    for screen in manifest.screens:
        target = screen.dump or default_dump_path(manifest.project_dir, screen.feature)
        if skip_existing and target.is_file():
            logger.info("Skipping existing dump for {} at {}", screen.feature, target.as_posix())
            written.append((screen, target))
            continue
        path = await dump_screen_node(
            connector,
            file_key=manifest.file_key,
            screen=screen,
            project_dir=manifest.project_dir,
        )
        written.append((screen, path))
    return written
