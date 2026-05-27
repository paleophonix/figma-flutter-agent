"""Reuse exported assets already present in a Flutter project."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.assets.optimize import svg_has_unsupported_filter
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
    icons_dir = project_dir / "assets" / "icons"
    if icons_dir.is_dir():
        for path in icons_dir.glob("*.svg"):
            node_id = node_id_from_asset_stem(path.stem)
            if node_id is None or node_id in excludes:
                continue
            svg_text = path.read_text(encoding="utf-8")
            entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/icons/{path.name}",
                    kind="icon",
                    svg_has_filter=svg_has_unsupported_filter(svg_text),
                )
            )

    images_dir = project_dir / "assets" / "images"
    if images_dir.is_dir():
        for path in images_dir.glob("*.png"):
            node_id = node_id_from_asset_stem(path.stem)
            if node_id is None or node_id in excludes:
                continue
            entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/images/{path.name}",
                    kind="image",
                )
            )

    return AssetManifest(entries=entries)
