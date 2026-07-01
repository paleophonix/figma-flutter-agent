"""Export SVG/PNG assets for an entire Figma file document."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.assets.collect import collect_exportable_nodes
from figma_flutter_agent.assets.exporter import AssetExporter
from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry
from figma_flutter_agent.config import AssetsConfig
from figma_flutter_agent.debug.paths import resolve_full_file_dump
from figma_flutter_agent.figma.client import FigmaConnector
from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.schemas import AssetManifest


@dataclass(frozen=True)
class AssetExportScope:
    """Which asset families to export for a batch dump run."""

    export_svg: bool
    export_raster: bool
    export_blur_png: bool


@dataclass(frozen=True)
class FileAssetExportResult:
    """Outcome of exporting all media assets for a Figma file."""

    manifest: AssetManifest
    icon_count: int
    raster_count: int
    exported_node_ids: frozenset[str]
    failed_node_ids: frozenset[str]
    rate_limited: bool


def load_cached_file_document(
    project_dir: Path, file_key: str
) -> tuple[dict[str, Any], str | None, Path]:
    """Load a cached full-file dump document tree.

    Args:
        project_dir: Flutter project root.
        file_key: Figma file key.

    Returns:
        Tuple of document node, optional file name, and cache path.

    Raises:
        FileNotFoundError: When the cache file is missing.
        ValueError: When the cached payload has no document node.
    """
    import json

    path = resolve_full_file_dump(project_dir, file_key)
    payload = json.loads(path.read_text(encoding="utf-8"))
    document = payload.get("document")
    if not isinstance(document, dict):
        msg = f"Cached dump at {path.as_posix()} does not contain a document node."
        raise ValueError(msg)
    file_name = payload.get("name")
    return document, file_name if isinstance(file_name, str) else None, path


async def export_assets_for_document(
    connector: FigmaConnector,
    *,
    file_key: str,
    document: dict[str, Any],
    project_dir: Path,
    assets: AssetsConfig,
    scope: AssetExportScope | None = None,
    skip_existing_assets: bool = False,
) -> FileAssetExportResult:
    """Export every exportable SVG/PNG asset under a Figma file document tree.

    Uses batched ``GET /v1/images/:file_key`` calls (20 node ids per request) for
    the whole file in one pass — not per screen.

    Args:
        connector: Active Figma connector.
        file_key: Figma file key.
        document: Raw Figma ``document`` node from ``GET /v1/files/:key``.
        project_dir: Flutter project root for ``assets/`` output.
        assets: Asset export settings from agent config.

    Returns:
        Export manifest and entry counts by kind.
    """
    exporter = AssetExporter(connector)
    export_scope = scope or AssetExportScope(
        export_svg=assets.svg,
        export_raster=True,
        export_blur_png=True,
    )
    from figma_flutter_agent.assets.eligibility import collect_raster_fallback_node_ids

    raster_fallback_node_ids = collect_raster_fallback_node_ids(document)
    outcome = await exporter.export_assets(
        file_key,
        document,
        project_dir,
        svg_enabled=export_scope.export_svg and assets.svg,
        raster_enabled=export_scope.export_raster,
        blur_png_fallback=export_scope.export_blur_png,
        png_scales=assets.png_scales,
        webp_enabled=assets.webp,
        illustrations_enabled=assets.illustrations,
        optimize_enabled=assets.optimize,
        continue_on_rate_limit=True,
        inter_batch_delay_sec=assets.images_batch_delay_sec,
        skip_existing_assets=skip_existing_assets,
        raster_fallback_node_ids=raster_fallback_node_ids,
    )
    manifest = outcome.manifest
    icon_count = sum(1 for entry in manifest.entries if entry.kind == "icon")
    raster_count = sum(1 for entry in manifest.entries if entry.kind in {"image", "illustration"})
    logger.info(
        "Exported {} SVG icon(s) and {} raster asset(s) for file {}",
        icon_count,
        raster_count,
        file_key,
    )

    asset_dirs = ["assets/icons/", "assets/images/"]
    if assets.illustrations:
        asset_dirs.append("assets/illustrations/")
    pubspec_batch = update_pubspec(
        project_dir,
        asset_dirs,
        needs_svg=export_scope.export_svg and assets.svg,
    )
    commit_pubspec_batch(pubspec_batch)

    if outcome.rate_limited:
        logger.warning(
            "Asset export hit Figma rate limits; {} node(s) could not be exported",
            len(outcome.failed_node_ids),
        )

    return FileAssetExportResult(
        manifest=manifest,
        icon_count=icon_count,
        raster_count=raster_count,
        exported_node_ids=outcome.exported_node_ids,
        failed_node_ids=outcome.failed_node_ids,
        rate_limited=outcome.rate_limited,
    )


def resolve_screen_dump_path(screen: ScreenEntry, project_dir: Path) -> Path:
    """Return the cached layout dump path for a manifest screen entry.

    Args:
        screen: Manifest screen entry.
        project_dir: Flutter project root.

    Returns:
        Absolute path to an existing raw dump, or the canonical target when missing.
    """
    from figma_flutter_agent.debug.paths import resolve_screen_raw_dump

    explicit = screen.dump if screen.dump is not None and screen.dump.is_file() else None
    return resolve_screen_raw_dump(
        project_dir,
        screen.feature,
        screen.node_id,
        explicit=explicit,
    )


def count_exportable_assets(
    document: dict[str, Any],
    assets: AssetsConfig,
) -> tuple[int, int]:
    """Count SVG icons and raster assets expected from a Figma document tree.

    Args:
        document: Figma frame or file document node.
        assets: Asset export settings.

    Returns:
        Tuple of ``(icon_count, raster_count)`` from ``collect_exportable_nodes``.
    """
    exportables = collect_exportable_nodes(
        document,
        illustrations_enabled=assets.illustrations,
    )
    icon_count = sum(1 for _node_id, _name, kind in exportables if kind == "icon")
    raster_count = sum(
        1
        for _node_id, _name, kind in exportables
        if kind in {"image", "illustration", "boundary_svg"}
    )
    return icon_count, raster_count


def asset_export_gap_hint(
    document: dict[str, Any],
    assets: AssetsConfig,
    result: FileAssetExportResult,
) -> str | None:
    """Return a user-facing hint when fewer assets were written than the dump expects.

    Args:
        document: Figma document used for export.
        assets: Asset export settings.
        result: Export outcome from ``export_assets_for_document``.

    Returns:
        Short warning string, or ``None`` when counts match or SVG export is disabled.
    """
    if not assets.svg:
        return None
    exportables = collect_exportable_nodes(
        document,
        illustrations_enabled=assets.illustrations,
    )
    expected_icon_ids = frozenset(node_id for node_id, _name, kind in exportables if kind == "icon")
    if not expected_icon_ids:
        return None
    covered = expected_icon_ids & result.exported_node_ids
    if len(covered) >= len(expected_icon_ids):
        return None
    if result.rate_limited:
        return (
            f"Figma rate limit: exported {len(covered)}/{len(expected_icon_ids)} icon(s). "
            "Retry list → assets export later."
        )
    if result.failed_node_ids:
        return (
            f"Exported {len(covered)}/{len(expected_icon_ids)} icon(s); "
            f"{len(result.failed_node_ids)} node(s) failed."
        )
    return (
        f"Expected {len(expected_icon_ids)} icon(s) from dump but wrote {len(covered)}. "
        "Try list → assets export."
    )


async def export_screen_assets_from_dump(
    connector: FigmaConnector,
    *,
    manifest: BatchManifest,
    screen: ScreenEntry,
    assets: AssetsConfig,
    skip_existing_assets: bool = False,
) -> FileAssetExportResult:
    """Export SVG/PNG assets for one screen using its cached layout dump only.

    Calls the Figma Images API; does not re-fetch the frame JSON from ``GET /v1/files``.

    Args:
        connector: Active Figma connector.
        manifest: Batch manifest containing ``file_key`` and ``project_dir``.
        screen: Screen entry whose dump JSON drives exportable node discovery.
        assets: Asset export settings from agent config.
        skip_existing_assets: When True, skip nodes whose target files already exist.

    Returns:
        Export manifest and entry counts by kind.

    Raises:
        FileNotFoundError: When the screen dump file is missing on disk.
        ValueError: When the dump JSON is not a valid document object.
    """
    import json

    dump_path = resolve_screen_dump_path(screen, manifest.project_dir)
    if not dump_path.is_file():
        msg = f"No cached dump for screen {screen.feature!r} at {dump_path.as_posix()}"
        raise FileNotFoundError(msg)
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Cached dump at {dump_path.as_posix()} is not a JSON object."
        raise ValueError(msg)
    return await export_assets_for_document(
        connector,
        file_key=manifest.file_key,
        document=payload,
        project_dir=manifest.project_dir,
        assets=assets,
        skip_existing_assets=skip_existing_assets,
    )
