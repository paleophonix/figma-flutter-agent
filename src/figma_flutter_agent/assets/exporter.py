from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from figma_flutter_agent.assets.boundaries import RenderBoundaryAssetExportMixin
from figma_flutter_agent.assets.collect import collect_exportable_nodes
from figma_flutter_agent.assets.directories import ensure_asset_directories
from figma_flutter_agent.assets.effects import index_figma_nodes, node_has_layer_blur
from figma_flutter_agent.assets.files import AssetFileDownloadMixin, rewrite_entries_to_webp
from figma_flutter_agent.assets.models import AssetExportOutcome
from figma_flutter_agent.assets.names import asset_filename
from figma_flutter_agent.assets.optimize import svg_has_unsupported_filter, svg_path_element_count
from figma_flutter_agent.figma.client import FigmaConnector
from figma_flutter_agent.schemas import AssetManifest, AssetManifestEntry


class AssetExporter(AssetFileDownloadMixin, RenderBoundaryAssetExportMixin):
    def __init__(self, connector: FigmaConnector) -> None:
        self._connector = connector

    async def export_assets(
        self,
        file_key: str,
        root: dict[str, Any],
        project_dir: Path,
        *,
        svg_enabled: bool = True,
        raster_enabled: bool = True,
        blur_png_fallback: bool = True,
        png_scales: list[int] | None = None,
        webp_enabled: bool = False,
        illustrations_enabled: bool = True,
        optimize_enabled: bool = True,
        continue_on_rate_limit: bool = True,
        inter_batch_delay_sec: float = 1.0,
        skip_existing_assets: bool = False,
        exclude_node_ids: set[str] | None = None,
        flatten_exclude_node_ids: set[str] | None = None,
        render_boundary_node_ids: set[str] | None = None,
    ) -> AssetExportOutcome:
        scales = png_scales or [1, 2, 3]
        exportables = collect_exportable_nodes(
            root,
            illustrations_enabled=illustrations_enabled,
            exclude_node_ids=exclude_node_ids,
            flatten_exclude_node_ids=flatten_exclude_node_ids,
            render_boundary_node_ids=render_boundary_node_ids,
        )
        manifest = AssetManifest()
        failed_node_ids: set[str] = set()
        rate_limited = False

        icons_dir, images_dir, illustrations_dir = ensure_asset_directories(project_dir)

        icon_ids = [
            node_id for node_id, _, kind in exportables if kind in {"icon", "boundary_svg"}
        ]
        exportable_by_id = {node_id: (name, kind) for node_id, name, kind in exportables}
        raster_exportables = [
            (node_id, name, kind)
            for node_id, name, kind in exportables
            if kind not in {"icon", "boundary_svg"}
        ]
        raster_ids = [node_id for node_id, _, _ in raster_exportables]
        figma_nodes = index_figma_nodes(root)

        async def _fetch_urls(
            node_ids: list[str],
            *,
            fmt: str,
            scale: float = 1.0,
        ) -> dict[str, str]:
            nonlocal rate_limited
            if not node_ids:
                return {}
            result = await self._connector.fetch_image_urls(
                file_key,
                node_ids,
                fmt=fmt,
                scale=scale,
                continue_on_rate_limit=continue_on_rate_limit,
                inter_batch_delay_sec=inter_batch_delay_sec,
            )
            failed_node_ids.update(result.failed_node_ids)
            rate_limited = rate_limited or result.rate_limited
            return result.urls

        filter_by_id: dict[str, bool] = {}
        baked_blur_icon_ids: set[str] = set()

        if svg_enabled and icon_ids:
            pending_icon_ids: list[str] = []
            for node_id, name, kind in exportables:
                if kind not in {"icon", "boundary_svg"}:
                    continue
                asset_dir = illustrations_dir if kind == "boundary_svg" else icons_dir
                target = asset_dir / asset_filename(name, node_id, "svg")
                if skip_existing_assets and target.is_file():
                    decoded = target.read_text(encoding="utf-8")
                    has_filter = svg_has_unsupported_filter(decoded)
                    path_count = svg_path_element_count(decoded)
                    filter_by_id[node_id] = has_filter
                    if kind == "boundary_svg":
                        asset_path = f"assets/illustrations/{target.name}"
                        entry_kind: Literal["icon", "illustration"] = "illustration"
                    else:
                        asset_path = f"assets/icons/{target.name}"
                        entry_kind = "icon"
                    manifest.entries.append(
                        AssetManifestEntry(
                            node_id=node_id,
                            asset_path=asset_path,
                            kind=entry_kind,
                            svg_has_filter=has_filter,
                            svg_path_count=path_count,
                        )
                    )
                    logger.info("Skipping existing SVG asset for node {}", node_id)
                    continue
                pending_icon_ids.append(node_id)

            icon_urls = await _fetch_urls(pending_icon_ids, fmt="svg")
            for node_id in pending_icon_ids:
                if node_id not in icon_urls:
                    failed_node_ids.add(node_id)
            icon_jobs: list[tuple[str, str, str, str, Path]] = []
            for node_id, name, kind in exportables:
                if kind not in {"icon", "boundary_svg"} or node_id not in icon_urls:
                    continue
                url = icon_urls[node_id]
                filename = asset_filename(name, node_id, "svg")
                asset_dir = illustrations_dir if kind == "boundary_svg" else icons_dir
                icon_jobs.append((node_id, name, kind, url, asset_dir / filename))
            if icon_jobs:

                async def _download_icon(
                    node_id: str,
                    url: str,
                    target: Path,
                ) -> tuple[str, bool]:
                    has_filter = await self._download_to_file(
                        url,
                        target,
                        optimize_svg_enabled=optimize_enabled,
                    )
                    return node_id, has_filter

                results = await asyncio.gather(
                    *[
                        _download_icon(node_id, url, target)
                        for node_id, _, _, url, target in icon_jobs
                    ]
                )
                filter_by_id = dict(results)
                for node_id, name, kind, _url, _target in icon_jobs:
                    filename = asset_filename(name, node_id, "svg")
                    if kind == "boundary_svg":
                        asset_path = f"assets/illustrations/{filename}"
                        entry_kind: Literal["icon", "illustration"] = "illustration"
                    else:
                        asset_path = f"assets/icons/{filename}"
                        entry_kind = "icon"
                    manifest.entries.append(
                        AssetManifestEntry(
                            node_id=node_id,
                            asset_path=asset_path,
                            kind=entry_kind,
                            svg_has_filter=filter_by_id.get(node_id, False),
                        )
                    )

            baked_blur_icon_ids = {
                node_id
                for node_id in icon_ids
                if filter_by_id.get(node_id, False)
                or node_has_layer_blur(figma_nodes.get(node_id, {}))
            }
        elif blur_png_fallback and icon_ids:
            baked_blur_icon_ids = {
                node_id
                for node_id in icon_ids
                if node_has_layer_blur(figma_nodes.get(node_id, {}))
            }

        if blur_png_fallback and baked_blur_icon_ids:
            pending_blur_ids: list[str] = []
            for node_id in sorted(baked_blur_icon_ids):
                name, _kind = exportable_by_id.get(node_id, ("vector", "icon"))
                target = images_dir / asset_filename(name, node_id, "png")
                if skip_existing_assets and target.is_file():
                    manifest.entries.append(
                        AssetManifestEntry(
                            node_id=node_id,
                            asset_path=f"assets/images/{target.name}",
                            kind="image",
                        )
                    )
                    logger.info("Skipping existing blur PNG fallback for node {}", node_id)
                    continue
                pending_blur_ids.append(node_id)

            png_urls = await _fetch_urls(
                pending_blur_ids,
                fmt="png",
                scale=2.0,
            )
            for node_id in pending_blur_ids:
                if node_id not in png_urls:
                    failed_node_ids.add(node_id)
            png_downloads: list[Coroutine[Any, Any, Any]] = []
            for node_id in pending_blur_ids:
                image_url = png_urls.get(node_id)
                if image_url is None:
                    logger.warning(
                        "PNG fallback export unavailable for blurred vector node {}",
                        node_id,
                    )
                    continue
                name, _kind = exportable_by_id.get(node_id, ("vector", "icon"))
                filename = asset_filename(name, node_id, "png")
                target = images_dir / filename
                png_downloads.append(self._download_to_file(image_url, target))
                manifest.entries.append(
                    AssetManifestEntry(
                        node_id=node_id,
                        asset_path=f"assets/images/{filename}",
                        kind="image",
                    )
                )
            if png_downloads:
                await asyncio.gather(*png_downloads)

        if raster_enabled:
            for scale in scales:
                if not raster_ids:
                    break
                pending_raster_ids: list[str] = []
                for node_id, name, kind in raster_exportables:
                    base_dir = illustrations_dir if kind == "illustration" else images_dir
                    scale_dir = base_dir if scale == 1 else base_dir / f"{scale}.0x"
                    target = scale_dir / asset_filename(name, node_id, "png")
                    if skip_existing_assets and target.is_file():
                        if scale == 1:
                            asset_prefix = (
                                "assets/illustrations"
                                if kind == "illustration"
                                else "assets/images"
                            )
                            manifest.entries.append(
                                AssetManifestEntry(
                                    node_id=node_id,
                                    asset_path=f"{asset_prefix}/{target.name}",
                                    kind=kind,
                                )
                            )
                        logger.info(
                            "Skipping existing raster asset for node {} at scale {}",
                            node_id,
                            scale,
                        )
                        continue
                    if node_id not in pending_raster_ids:
                        pending_raster_ids.append(node_id)

                image_urls = await _fetch_urls(pending_raster_ids, fmt="png", scale=float(scale))
                for node_id in pending_raster_ids:
                    if node_id not in image_urls:
                        failed_node_ids.add(node_id)
                image_downloads: list[Coroutine[Any, Any, Any]] = []
                for node_id, name, kind in raster_exportables:
                    base_dir = illustrations_dir if kind == "illustration" else images_dir
                    scale_dir = base_dir if scale == 1 else base_dir / f"{scale}.0x"
                    filename = asset_filename(name, node_id, "png")
                    target = scale_dir / filename
                    if skip_existing_assets and target.is_file():
                        continue
                    image_url = image_urls.get(node_id)
                    if image_url is None:
                        continue
                    scale_dir.mkdir(parents=True, exist_ok=True)
                    image_downloads.append(self._download_to_file(image_url, target))
                    if scale == 1:
                        asset_prefix = (
                            "assets/illustrations" if kind == "illustration" else "assets/images"
                        )
                        manifest.entries.append(
                            AssetManifestEntry(
                                node_id=node_id,
                                asset_path=f"{asset_prefix}/{filename}",
                                kind=kind,
                            )
                        )
                if image_downloads:
                    await asyncio.gather(*image_downloads)

        if webp_enabled:
            manifest.entries = rewrite_entries_to_webp(
                manifest.entries,
                project_dir=project_dir,
            )

        exported_node_ids = frozenset(entry.node_id for entry in manifest.entries)
        unresolved_failures = frozenset(
            node_id for node_id in failed_node_ids if node_id not in exported_node_ids
        )
        return AssetExportOutcome(
            manifest=manifest,
            exported_node_ids=exported_node_ids,
            failed_node_ids=unresolved_failures,
            rate_limited=rate_limited,
        )
