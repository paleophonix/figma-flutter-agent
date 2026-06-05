"""Asset export stage for the generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.assets.exporter import AssetExporter
from figma_flutter_agent.assets.screen_frame import (
    build_screen_frame_exclude_ids,
    filter_manifest,
    prune_screen_frame_assets,
    strip_screen_frame_assets_from_tree,
)
from figma_flutter_agent.config import AssetsConfig
from figma_flutter_agent.figma.connector import FigmaConnector
from figma_flutter_agent.parser.prototype import PrototypeLink
from figma_flutter_agent.schemas import (
    AssetManifest,
    AssetManifestEntry,
    CleanDesignTreeNode,
    merge_asset_manifests,
)


@dataclass
class AssetExportRequest:
    """Inputs required to export assets for a frame and its prototype destinations."""

    file_key: str
    figma_root: dict[str, Any]
    project_dir: Path
    assets: AssetsConfig
    prototype_links: list[PrototypeLink]
    frame_index: dict[str, dict[str, Any]]
    primary_node_id: str


def apply_asset_manifest(tree: CleanDesignTreeNode, manifest: AssetManifest) -> None:
    """Attach exported asset paths onto clean-tree nodes."""
    lookup: dict[str, list[AssetManifestEntry]] = {}
    for entry in manifest.entries:
        lookup.setdefault(entry.node_id, []).append(entry)

    def walk(node: CleanDesignTreeNode) -> None:
        for entry in lookup.get(node.id, []):
            if entry.kind == "icon":
                node.vector_asset_key = entry.asset_path
                node.vector_svg_has_filter = entry.svg_has_filter
                node.vector_svg_path_count = entry.svg_path_count
            elif entry.kind in {"image", "illustration"}:
                if node.render_boundary and entry.asset_path.endswith(".svg"):
                    node.vector_asset_key = entry.asset_path
                    node.vector_svg_has_filter = entry.svg_has_filter
                    node.vector_svg_path_count = entry.svg_path_count
                else:
                    node.image_asset_key = entry.asset_path
        for child in node.children:
            walk(child)

    walk(tree)


def finalize_screen_assets(
    *,
    project_dir: Path,
    clean_tree: CleanDesignTreeNode,
    destination_trees: dict[str, CleanDesignTreeNode],
    manifest: AssetManifest,
    primary_node_id: str,
    destination_node_ids: set[str],
) -> tuple[AssetManifest, frozenset[str]]:
    """Filter, prune, and strip screen-frame assets before codegen."""
    from figma_flutter_agent.assets.screen_frame import collect_blocked_asset_paths

    exclude_node_ids = build_screen_frame_exclude_ids(primary_node_id, destination_node_ids)
    blocked_paths = {
        entry.asset_path
        for entry in manifest.entries
        if entry.node_id in exclude_node_ids
    }
    blocked_paths.update(collect_blocked_asset_paths(project_dir, exclude_node_ids))
    prune_screen_frame_assets(project_dir, exclude_node_ids)
    filtered = filter_manifest(manifest, exclude_node_ids)
    strip_screen_frame_assets_from_tree(clean_tree, exclude_node_ids)
    for tree in destination_trees.values():
        strip_screen_frame_assets_from_tree(tree, exclude_node_ids)
    apply_asset_manifest(clean_tree, filtered)
    for tree in destination_trees.values():
        apply_asset_manifest(tree, filtered)
    from figma_flutter_agent.parser.render_boundary import resolve_render_boundary_asset_keys

    resolve_render_boundary_asset_keys(
        clean_tree,
        project_dir,
        filtered,
        strict=False,
    )
    for tree in destination_trees.values():
        resolve_render_boundary_asset_keys(tree, project_dir, filtered)
    return filtered, frozenset(blocked_paths)


async def export_missing_render_boundary_assets(
    connector: FigmaConnector,
    *,
    file_key: str,
    figma_root: dict[str, Any],
    project_dir: Path,
    node_ids: frozenset[str],
    optimize_enabled: bool = True,
) -> AssetManifest:
    """Export SVG composites for render-boundary nodes not yet present on disk."""
    if not node_ids:
        return AssetManifest()
    from figma_flutter_agent.assets.exporter import AssetExporter

    exporter = AssetExporter(connector)
    return await exporter.export_render_boundary_assets(
        file_key,
        figma_root,
        project_dir,
        node_ids=node_ids,
        optimize_enabled=optimize_enabled,
    )


async def export_figma_assets(
    connector: FigmaConnector,
    request: AssetExportRequest,
    *,
    flatten_exclude_node_ids: frozenset[str] | None = None,
    render_boundary_node_ids: frozenset[str] | None = None,
) -> AssetManifest:
    """Export assets for the primary frame and prototype destination frames.

    Args:
        connector: Active Figma API client.
        request: Frame roots, export settings, and prototype metadata.

    Returns:
        Combined asset manifest for all exported frames.
    """
    exporter = AssetExporter(connector)
    destination_node_ids = {link.destination_node_id for link in request.prototype_links}
    exclude_node_ids = build_screen_frame_exclude_ids(
        request.primary_node_id,
        destination_node_ids,
    )

    flatten_excludes = set(flatten_exclude_node_ids or ())
    boundary_exports = set(render_boundary_node_ids or ())
    primary_outcome = await exporter.export_assets(
        request.file_key,
        request.figma_root,
        request.project_dir,
        svg_enabled=request.assets.svg,
        png_scales=request.assets.png_scales,
        webp_enabled=request.assets.webp,
        illustrations_enabled=request.assets.illustrations,
        optimize_enabled=request.assets.optimize,
        continue_on_rate_limit=True,
        inter_batch_delay_sec=request.assets.images_batch_delay_sec,
        exclude_node_ids=exclude_node_ids,
        flatten_exclude_node_ids=flatten_excludes,
        render_boundary_node_ids=boundary_exports,
    )
    manifest = primary_outcome.manifest

    for node_id in destination_node_ids:
        if node_id == request.primary_node_id:
            continue
        destination_frame = request.frame_index.get(node_id)
        if not isinstance(destination_frame, dict):
            continue
        extra_outcome = await exporter.export_assets(
            request.file_key,
            destination_frame,
            request.project_dir,
            svg_enabled=request.assets.svg,
            png_scales=request.assets.png_scales,
            webp_enabled=request.assets.webp,
            illustrations_enabled=request.assets.illustrations,
            optimize_enabled=request.assets.optimize,
            continue_on_rate_limit=True,
            inter_batch_delay_sec=request.assets.images_batch_delay_sec,
            exclude_node_ids=exclude_node_ids,
            flatten_exclude_node_ids=flatten_excludes,
            render_boundary_node_ids=boundary_exports,
        )
        merge_asset_manifests(manifest, extra_outcome.manifest)

    prune_screen_frame_assets(request.project_dir, exclude_node_ids)
    return filter_manifest(manifest, exclude_node_ids)
