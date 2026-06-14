"""Regression tests for filter raster fallback asset resolution."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.parser.boundaries.assets import resolve_missing_image_asset_keys
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_resolve_filter_raster_fallback_keys_binds_png(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets" / "illustrations"
    assets_dir.mkdir(parents=True)
    png = assets_dir / "card_face.png"
    png.write_bytes(b"png")
    node = CleanDesignTreeNode(
        id="1",
        name="Card art",
        type=NodeType.STACK,
        sizing=Sizing(width=327.0, height=204.0),
        vector_asset_key="assets/illustrations/card_face.svg",
        vector_svg_has_filter=True,
    )
    resolve_missing_image_asset_keys(node, tmp_path)
    assert node.image_asset_key == "assets/illustrations/card_face.png"
