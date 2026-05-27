"""Tests for the asset export pipeline stage."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from figma_flutter_agent.assets.exporter import AssetExportOutcome
from figma_flutter_agent.config import AssetsConfig
from figma_flutter_agent.schemas import (
    AssetManifest,
    AssetManifestEntry,
    CleanDesignTreeNode,
    NodeType,
)
from figma_flutter_agent.stages.assets import (
    AssetExportRequest,
    apply_asset_manifest,
    export_figma_assets,
)


@pytest.mark.asyncio
async def test_export_figma_assets_merges_destination_manifest(tmp_path: Path) -> None:
    primary_root = {
        "id": "1:1",
        "name": "Screen",
        "type": "FRAME",
        "visible": True,
        "children": [
            {
                "id": "1:2",
                "name": "Logo",
                "type": "VECTOR",
                "visible": True,
            }
        ],
    }
    destination_root = {
        "id": "2:1",
        "name": "Details",
        "type": "FRAME",
        "visible": True,
        "children": [],
    }
    primary_manifest = AssetManifest(
        entries=[
            AssetManifestEntry(
                node_id="1:2",
                asset_path="assets/icons/logo_1_2.svg",
                kind="icon",
            )
        ]
    )
    destination_manifest = AssetManifest(
        entries=[
            AssetManifestEntry(
                node_id="2:1",
                asset_path="assets/images/details_2_1.png",
                kind="image",
            )
        ]
    )
    connector = MagicMock()

    with patch(
        "figma_flutter_agent.stages.assets.AssetExporter.export_assets",
        new=AsyncMock(
            side_effect=[
                AssetExportOutcome(
                    manifest=primary_manifest,
                    exported_node_ids=frozenset({"1:2"}),
                    failed_node_ids=frozenset(),
                    rate_limited=False,
                ),
                AssetExportOutcome(
                    manifest=destination_manifest,
                    exported_node_ids=frozenset({"2:1"}),
                    failed_node_ids=frozenset(),
                    rate_limited=False,
                ),
            ]
        ),
    ) as export_assets:
        manifest = await export_figma_assets(
            connector,
            AssetExportRequest(
                file_key="abc",
                figma_root=primary_root,
                project_dir=tmp_path,
                assets=AssetsConfig(),
                prototype_links=[MagicMock(destination_node_id="2:1")],
                frame_index={"2:1": destination_root},
                primary_node_id="1:1",
            ),
        )

    assert export_assets.await_count == 2
    assert len(manifest.entries) == 1
    assert {entry.node_id for entry in manifest.entries} == {"1:2"}


def test_apply_asset_manifest_sets_vector_and_image_keys() -> None:
    tree = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.CONTAINER,
        children=[
            CleanDesignTreeNode(id="1:2", name="Logo", type=NodeType.VECTOR),
            CleanDesignTreeNode(id="1:3", name="Hero", type=NodeType.IMAGE),
        ],
    )
    manifest = AssetManifest(
        entries=[
            AssetManifestEntry(
                node_id="1:2",
                asset_path="assets/icons/logo.svg",
                kind="icon",
            ),
            AssetManifestEntry(
                node_id="1:3",
                asset_path="assets/images/hero.png",
                kind="image",
            ),
        ]
    )

    apply_asset_manifest(tree, manifest)

    assert tree.children[0].vector_asset_key == "assets/icons/logo.svg"
    assert tree.children[1].image_asset_key == "assets/images/hero.png"


def test_apply_asset_manifest_sets_baked_png_for_blurred_icon() -> None:
    tree = CleanDesignTreeNode(
        id="1:3979",
        name="Vector",
        type=NodeType.VECTOR,
    )
    manifest = AssetManifest(
        entries=[
            AssetManifestEntry(
                node_id="1:3979",
                asset_path="assets/icons/vector_1_3979.svg",
                kind="icon",
                svg_has_filter=True,
            ),
            AssetManifestEntry(
                node_id="1:3979",
                asset_path="assets/images/vector_1_3979.png",
                kind="image",
            ),
        ]
    )

    apply_asset_manifest(tree, manifest)

    assert tree.vector_asset_key == "assets/icons/vector_1_3979.svg"
    assert tree.vector_svg_has_filter is True
    assert tree.image_asset_key == "assets/images/vector_1_3979.png"
