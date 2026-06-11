"""Import Figma files or single frames into a Flutter project manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.batch.asset_export import (
    FileAssetExportResult,
    export_assets_for_document,
    export_screen_assets_from_dump,
)
from figma_flutter_agent.batch.dump import dump_screen_node
from figma_flutter_agent.batch.dump_mode import BatchDumpMode
from figma_flutter_agent.batch.file_dump import dump_full_figma_file
from figma_flutter_agent.batch.manifest import (
    BatchManifest,
    ScreenEntry,
    default_dump_path,
    load_batch_manifest,
    write_batch_manifest,
)
from figma_flutter_agent.config import FontsConfig, load_settings
from figma_flutter_agent.dev.import_manifest import (
    find_manifest_screen_for_frame,
    resolve_import_feature_name,
    upsert_screen_in_manifest,
)
from figma_flutter_agent.figma.client import FigmaConnector
from figma_flutter_agent.figma.url import ParsedFigmaInput, build_figma_url
from figma_flutter_agent.fonts.sync import sync_fonts_from_figma_document


async def _load_frame_document(
    connector: FigmaConnector,
    parsed: ParsedFigmaInput,
) -> dict[str, Any]:
    """Fetch the Figma document JSON for a single frame node.

    Args:
        connector: Active Figma connector.
        parsed: Parsed frame-level Figma input.

    Returns:
        Frame node document dict.

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
    return node_payload.document


async def fetch_figma_frame_display_name(
    connector: FigmaConnector,
    parsed: ParsedFigmaInput,
) -> str:
    """Return the Figma layer name for a frame (used before interactive slug prompts).

    Args:
        connector: Active Figma connector.
        parsed: Parsed frame-level Figma input.

    Returns:
        Frame display name, or the node id when the layer has no name.

    Raises:
        ValueError: When the node cannot be fetched from Figma.
    """
    document = await _load_frame_document(connector, parsed)
    return str(document.get("name") or parsed.node_id)


async def export_figma_frame_assets(
    connector: FigmaConnector,
    parsed: ParsedFigmaInput,
    *,
    manifest_path: Path,
    skip_existing_assets: bool = False,
) -> tuple[str, FileAssetExportResult]:
    """Export SVG/PNG assets for one frame using its cached layout dump only.

    Args:
        connector: Active Figma connector.
        parsed: Parsed frame-level Figma input.
        manifest_path: Batch manifest path.
        skip_existing_assets: When True, skip nodes whose target files already exist.

    Returns:
        Tuple of ``(feature_slug, asset_export_result)``.

    Raises:
        ValueError: When the frame node id is missing or the screen is not in the manifest.
        FileNotFoundError: When ``screens.yaml`` or the cached dump is missing.
    """
    if parsed.node_id is None:
        msg = "Frame asset export requires a node id."
        raise ValueError(msg)
    if not manifest_path.is_file():
        msg = f"No manifest at {manifest_path.as_posix()}; fetch JSON first (all or json scope)."
        raise FileNotFoundError(msg)
    manifest = load_batch_manifest(manifest_path)
    screen = find_manifest_screen_for_frame(
        manifest,
        file_key=parsed.file_key,
        node_id=parsed.node_id,
    )
    if screen is None:
        msg = (
            f"Screen {parsed.node_id!r} is not in {manifest_path.as_posix()}; "
            "fetch JSON first (all or json scope)."
        )
        raise ValueError(msg)
    settings = load_settings()
    result = await export_screen_assets_from_dump(
        connector,
        manifest=manifest,
        screen=screen,
        assets=settings.agent.assets,
        skip_existing_assets=skip_existing_assets,
    )
    logger.info(
        "Frame asset export wrote {} SVG icon(s) and {} raster asset(s) for {}",
        result.icon_count,
        result.raster_count,
        screen.feature,
    )
    return screen.feature, result


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
    mode: BatchDumpMode = BatchDumpMode.ALL,
) -> tuple[str, Path, FileAssetExportResult | None]:
    """Fetch one frame, write its dump, optionally export assets, and upsert ``screens.yaml``.

    Args:
        connector: Active Figma connector.
        parsed: Parsed frame-level Figma input.
        project_dir: Flutter project root.
        manifest_path: Batch manifest path.
        feature_name: Optional feature slug override.
        merge: When True, merge into the existing manifest; when False, replace it.
        fonts: Optional font sync settings; defaults to agent config.
        mode: ``ALL`` fetches JSON and assets; ``JSON`` skips the Images API.

    Returns:
        Tuple of ``(feature_slug, dump_path, asset_export_result)``.

    Raises:
        ValueError: When the node cannot be fetched from Figma or ``mode`` is unsupported.
    """
    if mode not in {BatchDumpMode.ALL, BatchDumpMode.JSON}:
        msg = f"import_figma_frame does not support mode {mode!r}; use export_figma_frame_assets."
        raise ValueError(msg)
    document = await _load_frame_document(connector, parsed)
    frame_name = str(document.get("name") or parsed.node_id)
    if manifest_path.is_file():
        manifest = load_batch_manifest(manifest_path)
    else:
        manifest = BatchManifest(
            file_key=parsed.file_key,
            project_dir=project_dir,
            screens=(),
        )
    feature = resolve_import_feature_name(
        feature_name,
        frame_name,
        manifest,
        parsed.node_id,
    )

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

    asset_result: FileAssetExportResult | None = None
    if mode is BatchDumpMode.ALL:
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
