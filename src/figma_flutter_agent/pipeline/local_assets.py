"""Reuse exported assets already present in a Flutter project."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.assets.optimize import svg_has_unsupported_filter, svg_path_element_count
from figma_flutter_agent.assets.screen_frame import node_id_from_asset_stem
from figma_flutter_agent.schemas import AssetManifest, AssetManifestEntry


def local_asset_manifest_from_project(
    project_dir: Path,
    *,
    exclude_node_ids: frozenset[str] | None = None,
) -> AssetManifest:
    """Build an asset manifest from on-disk ``assets/icons`` and ``assets/images`` files."""
    excludes = exclude_node_ids or frozenset()
    entries: list[AssetManifestEntry] = []
    for svg_dir, kind in (("icons", "icon"), ("illustrations", "illustration")):
        asset_dir = project_dir / "assets" / svg_dir
        if not asset_dir.is_dir():
            continue
        for path in asset_dir.glob("*.svg"):
            node_id = node_id_from_asset_stem(path.stem)
            if node_id is None or node_id in excludes:
                continue
            svg_text = path.read_text(encoding="utf-8")
            entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/{svg_dir}/{path.name}",
                    kind=kind,
                    svg_has_filter=svg_has_unsupported_filter(svg_text),
                    svg_path_count=svg_path_element_count(svg_text),
                )
            )

    for directory, kind in (("images", "image"), ("illustrations", "illustration")):
        asset_dir = project_dir / "assets" / directory
        if not asset_dir.is_dir():
            continue
        for path in asset_dir.glob("*.png"):
            node_id = node_id_from_asset_stem(path.stem)
            if node_id is None or node_id in excludes:
                continue
            entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/{directory}/{path.name}",
                    kind=kind,
                )
            )

    return AssetManifest(entries=entries)
