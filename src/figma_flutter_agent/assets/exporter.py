"""Asset export pipeline for icons and images."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from figma_flutter_agent.assets.optimize import optimize_svg, svg_has_unsupported_filter
from figma_flutter_agent.figma.connector import FigmaConnector
from figma_flutter_agent.schemas import AssetManifest, AssetManifestEntry

AssetKind = Literal["icon", "image", "illustration"]

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_-]+")
_ILLUSTRATION_HINTS = ("illustration", "hero", "banner", "artwork")


def _safe_filename(name: str) -> str:
    cleaned = _SAFE_NAME.sub("_", name.strip().lower()).strip("_")
    return cleaned or "asset"


def _asset_filename(name: str, node_id: str, extension: str) -> str:
    """Build a collision-safe asset filename using the Figma node id."""
    node_suffix = node_id.replace(":", "_")
    return f"{_safe_filename(name)}_{node_suffix}.{extension}"


def _classify_raster_kind(name: str, *, illustrations_enabled: bool) -> AssetKind:
    """Classify raster assets as standard images or illustrations."""
    if not illustrations_enabled:
        return "image"
    lowered = name.lower()
    if any(hint in lowered for hint in _ILLUSTRATION_HINTS):
        return "illustration"
    return "image"


def _index_figma_nodes(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index raw Figma nodes by id for export-time effect inspection."""
    nodes: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any]) -> None:
        node_id = node.get("id")
        if isinstance(node_id, str):
            nodes[node_id] = node
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    return nodes


def _node_has_layer_blur(node: dict[str, Any]) -> bool:
    """Return True when a raw Figma node declares a visible layer blur effect."""
    for effect in node.get("effects") or []:
        if effect.get("type") == "LAYER_BLUR" and effect.get("visible", True):
            radius = effect.get("radius")
            if radius is None or float(radius) > 0:
                return True
    return False


def _write_webp_copy(png_path: Path) -> Path | None:
    """Convert a PNG asset to WebP when Pillow is available."""
    from figma_flutter_agent.assets.webp import webp_conversion_available

    if not webp_conversion_available():
        logger.warning("Pillow is not installed; skipping WebP conversion for {}", png_path.name)
        return None

    from PIL import Image

    webp_path = png_path.with_suffix(".webp")
    with Image.open(png_path) as image:
        image.save(webp_path, format="WEBP")
    return webp_path


def collect_exportable_nodes(
    root: dict[str, Any],
    *,
    illustrations_enabled: bool = True,
    exclude_node_ids: set[str] | None = None,
) -> list[tuple[str, str, AssetKind]]:
    """Collect exportable nodes as tuples of (id, name, kind)."""
    from figma_flutter_agent.assets.composite_icons import collect_figma_composite_icon_groups

    items: list[tuple[str, str, AssetKind]] = []
    excludes = exclude_node_ids or set()
    composite_parents, composite_skip = collect_figma_composite_icon_groups(root)

    def walk(node: dict[str, Any]) -> None:
        if node.get("visible") is False:
            return
        node_id = node.get("id")
        if not isinstance(node_id, str):
            return
        if node_id in excludes:
            for child in node.get("children") or []:
                walk(child)
            return
        if node_id in composite_skip:
            return
        node_type = node.get("type")
        raw_name = node.get("name")
        name = str(raw_name) if raw_name is not None else node_id
        if node_id in composite_parents:
            items.append((node_id, name, "icon"))
            return
        if node_type in {"VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "ELLIPSE", "POLYGON"}:
            items.append((node_id, name, "icon"))
        elif node_type == "RECTANGLE" and any(
            fill.get("type") == "IMAGE" for fill in (node.get("fills") or [])
        ):
            items.append(
                (
                    node_id,
                    name,
                    _classify_raster_kind(name, illustrations_enabled=illustrations_enabled),
                )
            )
        elif node.get("exportSettings"):
            if node_type in {"COMPONENT", "INSTANCE", "FRAME"}:
                items.append((node_id, name, "icon"))
            else:
                items.append(
                    (
                        node_id,
                        name,
                        _classify_raster_kind(name, illustrations_enabled=illustrations_enabled),
                    )
                )
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    return items


@dataclass(frozen=True)
class AssetExportOutcome:
    """Outcome of exporting assets for a Figma document subtree."""

    manifest: AssetManifest
    exported_node_ids: frozenset[str]
    failed_node_ids: frozenset[str]
    rate_limited: bool


class AssetExporter:
    """Export Figma assets into a Flutter project directory."""

    def __init__(self, connector: FigmaConnector) -> None:
        self._connector = connector

    async def _download_to_file(
        self, url: str, target: Path, *, optimize_svg_enabled: bool = False
    ) -> bool:
        """Download asset bytes to ``target``. Returns True when SVG has blur filters."""
        content = await self._connector.download_bytes(url)
        if optimize_svg_enabled and target.suffix.lower() == ".svg":
            decoded = content.decode("utf-8")
            target.write_text(optimize_svg(decoded), encoding="utf-8")
            return svg_has_unsupported_filter(decoded)
        target.write_bytes(content)
        return False

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
    ) -> AssetExportOutcome:
        """Export icons, images, and illustrations into the Flutter project assets folder."""
        scales = png_scales or [1, 2, 3]
        exportables = collect_exportable_nodes(
            root,
            illustrations_enabled=illustrations_enabled,
            exclude_node_ids=exclude_node_ids,
        )
        manifest = AssetManifest()
        failed_node_ids: set[str] = set()
        rate_limited = False

        icons_dir = project_dir / "assets" / "icons"
        images_dir = project_dir / "assets" / "images"
        illustrations_dir = project_dir / "assets" / "illustrations"
        icons_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        illustrations_dir.mkdir(parents=True, exist_ok=True)

        icon_ids = [node_id for node_id, _, kind in exportables if kind == "icon"]
        exportable_by_id = {node_id: (name, kind) for node_id, name, kind in exportables}
        raster_exportables = [
            (node_id, name, kind) for node_id, name, kind in exportables if kind != "icon"
        ]
        raster_ids = [node_id for node_id, _, _ in raster_exportables]
        figma_nodes = _index_figma_nodes(root)

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
                if kind != "icon":
                    continue
                target = icons_dir / _asset_filename(name, node_id, "svg")
                if skip_existing_assets and target.is_file():
                    decoded = target.read_text(encoding="utf-8")
                    has_filter = svg_has_unsupported_filter(decoded)
                    filter_by_id[node_id] = has_filter
                    manifest.entries.append(
                        AssetManifestEntry(
                            node_id=node_id,
                            asset_path=f"assets/icons/{target.name}",
                            kind="icon",
                            svg_has_filter=has_filter,
                        )
                    )
                    logger.info("Skipping existing SVG asset for node {}", node_id)
                    continue
                pending_icon_ids.append(node_id)

            icon_urls = await _fetch_urls(pending_icon_ids, fmt="svg")
            for node_id in pending_icon_ids:
                if node_id not in icon_urls:
                    failed_node_ids.add(node_id)
            icon_jobs: list[tuple[str, str, str, Path]] = []
            for node_id, name, kind in exportables:
                if kind != "icon" or node_id not in icon_urls:
                    continue
                url = icon_urls[node_id]
                filename = _asset_filename(name, node_id, "svg")
                icon_jobs.append((node_id, name, url, icons_dir / filename))
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
                    *[_download_icon(node_id, url, target) for node_id, _, url, target in icon_jobs]
                )
                filter_by_id = dict(results)
                for node_id, name, _, _target in icon_jobs:
                    filename = _asset_filename(name, node_id, "svg")
                    manifest.entries.append(
                        AssetManifestEntry(
                            node_id=node_id,
                            asset_path=f"assets/icons/{filename}",
                            kind="icon",
                            svg_has_filter=filter_by_id.get(node_id, False),
                        )
                    )

            baked_blur_icon_ids = {
                node_id
                for node_id in icon_ids
                if filter_by_id.get(node_id, False)
                or _node_has_layer_blur(figma_nodes.get(node_id, {}))
            }
        elif blur_png_fallback and icon_ids:
            baked_blur_icon_ids = {
                node_id
                for node_id in icon_ids
                if _node_has_layer_blur(figma_nodes.get(node_id, {}))
            }

        if blur_png_fallback and baked_blur_icon_ids:
            pending_blur_ids: list[str] = []
            for node_id in sorted(baked_blur_icon_ids):
                name, _kind = exportable_by_id.get(node_id, ("vector", "icon"))
                target = images_dir / _asset_filename(name, node_id, "png")
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
                filename = _asset_filename(name, node_id, "png")
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
                    target = scale_dir / _asset_filename(name, node_id, "png")
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
                    filename = _asset_filename(name, node_id, "png")
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
            updated_entries: list[AssetManifestEntry] = []
            for entry in manifest.entries:
                if entry.kind not in {"image", "illustration"}:
                    updated_entries.append(entry)
                    continue
                png_path = project_dir.joinpath(*entry.asset_path.split("/"))
                if not png_path.is_file():
                    updated_entries.append(entry)
                    continue
                webp_path = _write_webp_copy(png_path)
                if webp_path is None:
                    updated_entries.append(entry)
                    continue
                updated_entries.append(
                    AssetManifestEntry(
                        node_id=entry.node_id,
                        asset_path=entry.asset_path.replace(".png", ".webp"),
                        kind=entry.kind,
                    )
                )
            manifest.entries = updated_entries

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
