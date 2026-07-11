"""Render-boundary asset export."""

from __future__ import annotations

import shutil
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
        unavailable_node_ids: list[str] = []
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
            await self._export_render_boundary_primary_rasters(
                file_key,
                node_ids=node_ids,
                figma_nodes=figma_nodes,
                project_dir=project_dir,
                manifest=manifest,
                continue_on_rate_limit=continue_on_rate_limit,
            )
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
                unavailable_node_ids.append(node_id)
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
        await self._export_render_boundary_primary_rasters(
            file_key,
            node_ids=node_ids,
            figma_nodes=figma_nodes,
            project_dir=project_dir,
            manifest=manifest,
            continue_on_rate_limit=continue_on_rate_limit,
        )
        await self._export_render_boundary_raster_fallbacks(
            file_key,
            manifest=manifest,
            illustrations_dir=illustrations_dir,
            continue_on_rate_limit=continue_on_rate_limit,
        )
        if unavailable_node_ids:
            logger.warning(
                "Render-boundary SVG export unavailable for {} node(s): {}",
                len(unavailable_node_ids),
                ", ".join(unavailable_node_ids[:12]),
            )
        return manifest

    async def _export_render_boundary_primary_rasters(
        self,
        file_key: str,
        *,
        node_ids: frozenset[str],
        figma_nodes: dict,
        project_dir: Path,
        manifest: AssetManifest,
        continue_on_rate_limit: bool,
    ) -> None:
        """Export PNG rasters for render-boundary hosts and semantic binding targets."""
        from figma_flutter_agent.parser.boundaries.assets import render_boundary_raster_asset_path
        from figma_flutter_agent.pipeline.local_assets import load_project_asset_bindings

        bindings = load_project_asset_bindings(project_dir)
        binding_by_node_id = {bound_id: filename for filename, bound_id in bindings.items()}
        images_dir = project_dir / "assets" / "images"
        illustrations_dir = project_dir / "assets" / "illustrations"
        images_dir.mkdir(parents=True, exist_ok=True)
        illustrations_dir.mkdir(parents=True, exist_ok=True)

        def _binding_probe_ids(node_id: str) -> list[str]:
            probe_ids = [node_id]
            node = figma_nodes.get(node_id)
            if not isinstance(node, dict):
                return probe_ids
            for child in node.get("children") or []:
                if child.get("visible") is False:
                    continue
                child_id = child.get("id")
                if isinstance(child_id, str) and child_id not in probe_ids:
                    probe_ids.append(child_id)
            return probe_ids

        pending_by_node: dict[str, list[tuple[Path, str]]] = {}
        for node_id in sorted(node_ids):
            targets: dict[Path, str] = {}
            canonical_rel = render_boundary_raster_asset_path(node_id)
            targets[project_dir / Path(canonical_rel)] = canonical_rel.replace("\\", "/")
            for probe_id in _binding_probe_ids(node_id):
                bound_filename = binding_by_node_id.get(probe_id)
                if bound_filename is None:
                    continue
                bound_rel = f"assets/images/{bound_filename}".replace("\\", "/")
                targets[images_dir / bound_filename] = bound_rel
            node = figma_nodes.get(node_id)
            raw_name = node.get("name") if isinstance(node, dict) else None
            name = str(raw_name) if raw_name is not None else node_id
            illustration_name = asset_filename(name, node_id, "png")
            illustration_rel = f"assets/illustrations/{illustration_name}"
            targets[illustrations_dir / illustration_name] = illustration_rel
            for target_path, rel_path in targets.items():
                if target_path.is_file():
                    if not any(
                        item.node_id == node_id and item.asset_path == rel_path
                        for item in manifest.entries
                    ):
                        manifest.entries.append(
                            AssetManifestEntry(
                                node_id=node_id,
                                asset_path=rel_path,
                                kind="image",
                            )
                        )
                    continue
                pending_by_node.setdefault(node_id, []).append((target_path, rel_path))

        if not pending_by_node:
            return

        result = await self._connector.fetch_image_urls(
            file_key,
            sorted(pending_by_node),
            fmt="png",
            continue_on_rate_limit=continue_on_rate_limit,
        )
        for node_id, targets in pending_by_node.items():
            url = result.urls.get(node_id)
            if url is None:
                logger.warning("Render-boundary PNG export unavailable for node {}", node_id)
                continue
            primary_target, primary_rel = targets[0]
            await self._download_to_file(url, primary_target, optimize_svg_enabled=False)
            manifest.entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=primary_rel,
                    kind="image",
                )
            )
            for extra_target, extra_rel in targets[1:]:
                if extra_target.is_file():
                    continue
                extra_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(primary_target, extra_target)
                if not any(
                    item.node_id == node_id and item.asset_path == extra_rel
                    for item in manifest.entries
                ):
                    manifest.entries.append(
                        AssetManifestEntry(
                            node_id=node_id,
                            asset_path=extra_rel,
                            kind="image",
                        )
                    )

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
