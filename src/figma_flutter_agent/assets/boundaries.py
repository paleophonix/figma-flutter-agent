"""Render-boundary asset export."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.assets.effects import index_figma_nodes
from figma_flutter_agent.assets.names import asset_filename
from figma_flutter_agent.assets.optimize import (
    svg_has_unsupported_filter,
    svg_path_element_count,
)
from figma_flutter_agent.generator.layout.widgets.svg import SVG_PATH_RASTER_THRESHOLD
from figma_flutter_agent.schemas import AssetManifest, AssetManifestEntry


def _render_boundary_needs_raster_fallback(
    *,
    svg_has_filter: bool,
    svg_path_count: int | None,
) -> bool:
    """Return True when a render-boundary SVG should also export a PNG raster."""
    if svg_has_filter:
        return True
    return svg_path_count is not None and svg_path_count > SVG_PATH_RASTER_THRESHOLD


class RenderBoundaryAssetExportMixin:
    async def export_render_boundary_assets(
        self,
        file_key: str,
        root: dict,
        project_dir: Path,
        *,
        node_ids: frozenset[str],
        optimize_enabled: bool = True,
        continue_on_rate_limit: bool = True,
    ) -> AssetManifest:
        """Export composite SVGs for explicit render-boundary node ids."""
        if not node_ids:
            return AssetManifest()
        figma_nodes = index_figma_nodes(root)
        illustrations_dir = project_dir / "assets" / "illustrations"
        illustrations_dir.mkdir(parents=True, exist_ok=True)
        manifest = AssetManifest()
        pending: list[tuple[str, str, Path]] = []
        for node_id in sorted(node_ids):
            node = figma_nodes.get(node_id)
            if not isinstance(node, dict):
                continue
            raw_name = node.get("name")
            name = str(raw_name) if raw_name is not None else node_id
            filename = asset_filename(name, node_id, "svg")
            target = illustrations_dir / filename
            if target.is_file():
                decoded = target.read_text(encoding="utf-8")
                has_filter = svg_has_unsupported_filter(decoded)
                path_count = svg_path_element_count(decoded)
                manifest.entries.append(
                    AssetManifestEntry(
                        node_id=node_id,
                        asset_path=f"assets/illustrations/{filename}",
                        kind="illustration",
                        svg_has_filter=has_filter,
                        svg_path_count=path_count,
                    )
                )
                continue
            pending.append((node_id, name, target))

        if not pending:
            await self._export_render_boundary_raster_fallbacks(
                file_key,
                manifest=manifest,
                illustrations_dir=illustrations_dir,
                continue_on_rate_limit=continue_on_rate_limit,
            )
            return manifest

        result = await self._connector.fetch_image_urls(
            file_key,
            [node_id for node_id, _, _ in pending],
            fmt="svg",
            continue_on_rate_limit=continue_on_rate_limit,
        )
        for node_id, name, target in pending:
            url = result.urls.get(node_id)
            if url is None:
                logger.warning("Render-boundary SVG export unavailable for node {}", node_id)
                continue
            has_filter = await self._download_to_file(
                url,
                target,
                optimize_svg_enabled=optimize_enabled,
            )
            path_count = svg_path_element_count(target.read_text(encoding="utf-8"))
            manifest.entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/illustrations/{asset_filename(name, node_id, 'svg')}",
                    kind="illustration",
                    svg_has_filter=has_filter,
                    svg_path_count=path_count,
                )
            )
        await self._export_render_boundary_raster_fallbacks(
            file_key,
            manifest=manifest,
            illustrations_dir=illustrations_dir,
            continue_on_rate_limit=continue_on_rate_limit,
        )
        return manifest

    async def _export_render_boundary_raster_fallbacks(
        self,
        file_key: str,
        *,
        manifest: AssetManifest,
        illustrations_dir: Path,
        continue_on_rate_limit: bool,
    ) -> None:
        """Export PNG fallbacks for complex render-boundary SVG illustrations."""
        pending_png: list[tuple[str, str, Path]] = []
        for entry in manifest.entries:
            if not entry.asset_path.endswith(".svg"):
                continue
            if not _render_boundary_needs_raster_fallback(
                svg_has_filter=entry.svg_has_filter,
                svg_path_count=entry.svg_path_count,
            ):
                continue
            png_name = Path(entry.asset_path).name.replace(".svg", ".png")
            png_target = illustrations_dir / png_name
            png_path = f"assets/illustrations/{png_name}"
            if png_target.is_file():
                if not any(
                    item.node_id == entry.node_id and item.asset_path == png_path
                    for item in manifest.entries
                ):
                    manifest.entries.append(
                        AssetManifestEntry(
                            node_id=entry.node_id,
                            asset_path=png_path,
                            kind="image",
                        )
                    )
                continue
            pending_png.append((entry.node_id, png_name, png_target))
        if not pending_png:
            return
        result = await self._connector.fetch_image_urls(
            file_key,
            [node_id for node_id, _, _ in pending_png],
            fmt="png",
            continue_on_rate_limit=continue_on_rate_limit,
        )
        for node_id, png_name, png_target in pending_png:
            url = result.urls.get(node_id)
            if url is None:
                logger.warning("Render-boundary PNG fallback unavailable for node {}", node_id)
                continue
            await self._download_to_file(url, png_target, optimize_svg_enabled=False)
            manifest.entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/illustrations/{png_name}",
                    kind="image",
                )
            )
