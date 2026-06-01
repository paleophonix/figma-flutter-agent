"""Import Figma files or single frames into a Flutter project manifest."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from figma_flutter_agent.batch.asset_export import FileAssetExportResult, export_assets_for_document
from figma_flutter_agent.batch.dump import dump_screen_node
from figma_flutter_agent.batch.file_dump import dump_full_figma_file
from figma_flutter_agent.batch.manifest import (
    BatchManifest,
    ScreenEntry,
    default_dump_path,
    load_batch_manifest,
    write_batch_manifest,
)
from figma_flutter_agent.config import FontsConfig, load_settings
from figma_flutter_agent.figma.connector import FigmaConnector
from figma_flutter_agent.figma.url import ParsedFigmaInput, build_figma_url
from figma_flutter_agent.fonts.sync import sync_fonts_from_figma_document
from figma_flutter_agent.generator.layout_common import to_snake_case


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


def upsert_screen_in_manifest(
    manifest_path: Path,
    *,
    project_dir: Path,
    file_key: str,
    screen: ScreenEntry,
) -> BatchManifest:
    """Insert or replace one screen entry in ``screens.yaml``.

    Args:
        manifest_path: Target manifest path.
        project_dir: Flutter project root stored in the manifest.
        file_key: Figma file key for the manifest header.
        screen: Screen entry to upsert (matched by ``node_id``).

    Returns:
        Updated manifest written to ``manifest_path``.
    """
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


async def import_figma_file(
    connector: FigmaConnector,
    parsed: ParsedFigmaInput,
    *,
    project_dir: Path,
    manifest_path: Path | None = None,
) -> int:
    """Dump an entire Figma file and write ``screens.yaml``.

    Args:
        connector: Active Figma connector.
        parsed: Parsed file-level Figma input.
        project_dir: Flutter project root.
        manifest_path: Optional manifest destination.

    Returns:
        Number of screen dumps written or reused.
    """
    result = await dump_full_figma_file(
        connector,
        file_key=parsed.file_key,
        project_dir=project_dir,
        manifest_path=manifest_path,
        with_assets=True,
    )
    return len(result.screens)


async def import_figma_frame(
    connector: FigmaConnector,
    parsed: ParsedFigmaInput,
    *,
    project_dir: Path,
    manifest_path: Path,
    feature_name: str | None = None,
    merge: bool = True,
    fonts: FontsConfig | None = None,
) -> tuple[str, Path, FileAssetExportResult | None]:
    """Fetch one frame, write its dump, export assets, and upsert ``screens.yaml``.

    Args:
        connector: Active Figma connector.
        parsed: Parsed frame-level Figma input.
        project_dir: Flutter project root.
        manifest_path: Batch manifest path.
        feature_name: Optional feature slug override.
        merge: When True, merge into the existing manifest; when False, replace it.
        fonts: Optional font sync settings; defaults to agent config.

    Returns:
        Tuple of ``(feature_slug, dump_path, asset_export_result)``.

    Raises:
        ValueError: When the node cannot be fetched from Figma.
    """
    if parsed.node_id is None:
        msg = "Frame import requires a node id."
        raise ValueError(msg)

    response = await connector.fetch_nodes(parsed.file_key, [parsed.node_id])
    node_payload = response.nodes.get(parsed.node_id)
    if node_payload is None or node_payload.document is None:
        msg = f"Node {parsed.node_id} was not found in Figma file {parsed.file_key}"
        raise ValueError(msg)

    frame_name = str(node_payload.document.get("name") or parsed.node_id)
    provisional = feature_name or to_snake_case(frame_name)
    if manifest_path.is_file():
        manifest = load_batch_manifest(manifest_path)
        feature = _unique_feature_name(provisional, manifest, parsed.node_id)
    else:
        feature = provisional or f"screen_{parsed.node_id.replace(':', '_')}"

    dump_path = default_dump_path(project_dir, feature)
    screen = ScreenEntry(
        feature=feature,
        node_id=parsed.node_id,
        dump=dump_path,
        figma_url=build_figma_url(parsed.file_key, parsed.node_id),
    )
    await dump_screen_node(
        connector,
        file_key=parsed.file_key,
        screen=screen,
        project_dir=project_dir,
    )
    if merge:
        upsert_screen_in_manifest(
            manifest_path,
            project_dir=project_dir,
            file_key=parsed.file_key,
            screen=screen,
        )
    else:
        write_batch_manifest(
            manifest_path,
            BatchManifest(
                file_key=parsed.file_key,
                project_dir=project_dir,
                screens=(screen,),
            ),
        )
        logger.info(
            "Replaced manifest with screen {} ({}) in {}",
            screen.feature,
            screen.node_id,
            manifest_path.as_posix(),
        )

    settings = load_settings()
    font_settings = fonts if fonts is not None else settings.agent.fonts
    document = json.loads(dump_path.read_text(encoding="utf-8"))
    sync_fonts_from_figma_document(project_dir, document, font_settings)

    asset_result = await export_assets_for_document(
        connector,
        file_key=parsed.file_key,
        document=document,
        project_dir=project_dir,
        assets=settings.agent.assets,
    )
    logger.info(
        "Frame fetch exported {} SVG icon(s) and {} raster asset(s) for {}",
        asset_result.icon_count,
        asset_result.raster_count,
        feature,
    )
    return feature, dump_path, asset_result
