"""Regression laws from niyama_order_2 batch repair (generic, not screen-patched)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.parser.boundaries.assets import (
    discover_asset_path_for_node,
    lookup_asset_path_for_component_vector_family,
)
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    Sizing,
)


def test_component_vector_family_skips_adjacent_icon_library_ids(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "vector_1162_10106.svg").write_text("<svg></svg>", encoding="utf-8")
    asset_index = {"1162_10106": "assets/icons/vector_1162_10106.svg"}
    map_variant = "I3561:43011;1435:18098;1162:10099"
    assert lookup_asset_path_for_component_vector_family(asset_index, map_variant) is None
    assert discover_asset_path_for_node(tmp_path, map_variant) is None
    cutlery_variant = "I3561:42994;1406:12001;1162:10248"
    assert (
        lookup_asset_path_for_component_vector_family(asset_index, cutlery_variant)
        == "assets/icons/vector_1162_10106.svg"
    )


def test_semantic_raster_binds_product_thumbnail_by_title_word(tmp_path: Path) -> None:
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    (images / "ramen-chicken.png").write_bytes(b"png")
    img = CleanDesignTreeNode(
        id="1:img",
        name="Img",
        type=NodeType.IMAGE,
        sizing=Sizing(width=76.0, height=76.0),
    )
    title = CleanDesignTreeNode(
        id="1:title",
        name="Title",
        type=NodeType.TEXT,
        text="Вок рамен с курицей\nв кисло-сладком соусе",
    )
    body = CleanDesignTreeNode(
        id="1:body",
        name="Body",
        type=NodeType.COLUMN,
        children=[title],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Card",
        type=NodeType.ROW,
        children=[img, body],
    )
    root = CleanDesignTreeNode(
        id="1:root",
        name="Order product",
        type=NodeType.STACK,
        variant=ComponentVariant(
            component_id="3481:34945",
            component_name="Order product",
            variant_properties={"Order product": "Inorder"},
        ),
        children=[row],
    )
    manifest = local_asset_manifest_from_project(tmp_path, clean_tree=root)
    image_entries = [entry for entry in manifest.entries if entry.kind == "image"]
    assert len(image_entries) == 1
    assert image_entries[0].node_id == "1:img"
    assert image_entries[0].asset_path == "assets/images/ramen-chicken.png"
