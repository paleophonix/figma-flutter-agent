"""Wizard helpers to export missing screen assets from a cached dump."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager

from loguru import logger

from figma_flutter_agent.assets.exporter import AssetExporter
from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids
from figma_flutter_agent.batch.asset_export import FileAssetExportResult
from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.run import RunScreenPlan
from figma_flutter_agent.dev.wizard.asset_gap import ScreenAssetGapPartition
from figma_flutter_agent.figma.client import FigmaConnector
from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.parser.boundaries.assets import collect_render_boundary_asset_plan
from figma_flutter_agent.pipeline.dump_prefetch import ScreenDumpPrefetch


@contextmanager
def _quiet_asset_export_logs() -> Iterator[None]:
    """Suppress noisy exporter INFO lines in the interactive wizard."""
    disabled = (
        "figma_flutter_agent.assets.exporter",
        "figma_flutter_agent.figma.endpoints.images",
        "figma_flutter_agent.assets.reporting",
    )
    for name in disabled:
        logger.disable(name)
    try:
        yield
    finally:
        for name in disabled:
            logger.enable(name)


def _file_export_result(
    outcome: object,
    *,
    project_dir,
    assets,
) -> FileAssetExportResult:
    from figma_flutter_agent.batch.asset_export import AssetExportScope

    manifest = outcome.manifest
    icon_count = sum(1 for entry in manifest.entries if entry.kind == "icon")
    raster_count = sum(1 for entry in manifest.entries if entry.kind in {"image", "illustration"})
    asset_dirs = ["assets/icons/", "assets/images/"]
    if assets.illustrations:
        asset_dirs.append("assets/illustrations/")
    scope = AssetExportScope(export_svg=assets.svg, export_raster=True, export_blur_png=True)
    pubspec_batch = update_pubspec(
        project_dir,
        asset_dirs,
        needs_svg=scope.export_svg and assets.svg,
    )
    commit_pubspec_batch(pubspec_batch)
    return FileAssetExportResult(
        manifest=manifest,
        icon_count=icon_count,
        raster_count=raster_count,
        exported_node_ids=outcome.exported_node_ids,
        failed_node_ids=outcome.failed_node_ids,
        rate_limited=outcome.rate_limited,
    )


async def export_missing_screen_assets(
    plan: RunScreenPlan,
    settings: Settings,
    *,
    gap_partition: ScreenAssetGapPartition,
    dump_prefetch: ScreenDumpPrefetch | None = None,
) -> FileAssetExportResult:
    """Export missing screen icons: SVG for downloadable gaps, PNG for API-skip icons.

    Args:
        plan: Resolved manifest screen plan with dump path.
        settings: Agent settings (Figma token, asset policy).
        gap_partition: Partitioned missing export ids from preflight/check.
        dump_prefetch: Optional parsed dump snapshot for screen-scoped collect.

    Returns:
        File-level export outcome with counts and failed node ids.

    Raises:
        RuntimeError: When ``FIGMA_ACCESS_TOKEN`` is missing or nothing is missing.
        FileNotFoundError: When the screen dump is missing.
    """
    svg_target_ids = gap_partition.downloadable_missing_ids
    raster_target_ids = gap_partition.api_unexportable_ids
    target_ids = svg_target_ids | raster_target_ids
    if not target_ids:
        msg = "No missing assets to sync for this screen"
        raise RuntimeError(msg)

    token = settings.figma_token().strip()
    if not token:
        msg = "FIGMA_ACCESS_TOKEN is required to download assets from Figma"
        raise RuntimeError(msg)

    if dump_prefetch is None or not dump_prefetch.matches_dump(plan.dump_path):
        from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump
        from figma_flutter_agent.stages.parse import parse_figma_frame

        fetch_result = load_fetch_result_from_dump(
            plan.dump_path,
            file_key=plan.manifest.file_key,
            node_id=plan.screen.node_id,
        )
        parse_result = parse_figma_frame(fetch_result)
    else:
        fetch_result = dump_prefetch.fetch_result
        parse_result = dump_prefetch.parse_result

    exclude_node_ids = build_screen_frame_exclude_ids(plan.screen.node_id)
    boundary_exports, flatten_excludes = collect_render_boundary_asset_plan(
        parse_result.clean_tree,
    )
    assets = settings.agent.assets

    async with FigmaConnector(token, settings.figma_api_base_url) as connector:
        exporter = AssetExporter(connector)
        with _quiet_asset_export_logs():
            outcome = await exporter.export_assets(
                plan.manifest.file_key,
                fetch_result.root,
                plan.project_dir,
                svg_enabled=assets.svg,
                raster_enabled=True,
                blur_png_fallback=True,
                png_scales=assets.png_scales,
                webp_enabled=assets.webp,
                illustrations_enabled=assets.illustrations,
                optimize_enabled=assets.optimize,
                inter_batch_delay_sec=assets.images_batch_delay_sec,
                skip_existing_assets=True,
                exclude_node_ids=set(exclude_node_ids),
                flatten_exclude_node_ids=set(flatten_excludes),
                render_boundary_node_ids=set(boundary_exports),
                restrict_node_ids=target_ids,
                raster_fallback_node_ids=raster_target_ids,
            )

    return _file_export_result(
        outcome,
        project_dir=plan.project_dir,
        assets=assets,
    )


def run_export_missing_screen_assets(
    plan: RunScreenPlan,
    settings: Settings,
    *,
    gap_partition: ScreenAssetGapPartition,
    dump_prefetch: ScreenDumpPrefetch | None = None,
) -> FileAssetExportResult:
    """Sync wrapper for :func:`export_missing_screen_assets`."""
    result = asyncio.run(
        export_missing_screen_assets(
            plan,
            settings,
            gap_partition=gap_partition,
            dump_prefetch=dump_prefetch,
        )
    )
    logger.info(
        "Wizard asset sync for {}: {} SVG, {} raster ({} svg + {} raster target(s), {} failed)",
        plan.screen.feature,
        result.icon_count,
        result.raster_count,
        len(gap_partition.downloadable_missing_ids),
        len(gap_partition.api_unexportable_ids),
        len(result.failed_node_ids),
    )
    return result
