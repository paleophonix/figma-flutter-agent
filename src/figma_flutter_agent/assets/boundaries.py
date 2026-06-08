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
from figma_flutter_agent.schemas import AssetManifest, AssetManifestEntry


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
                manifest.entries.append(
                    AssetManifestEntry(
                        node_id=node_id,
                        asset_path=f"assets/illustrations/{filename}",
                        kind="illustration",
                        svg_has_filter=svg_has_unsupported_filter(decoded),
                        svg_path_count=svg_path_element_count(decoded),
                    )
                )
                continue
            pending.append((node_id, name, target))

        if not pending:
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
            manifest.entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/illustrations/{asset_filename(name, node_id, 'svg')}",
                    kind="illustration",
                    svg_has_filter=has_filter,
                )
            )
        return manifest
