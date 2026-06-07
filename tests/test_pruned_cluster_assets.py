"""Resolve per-instance SVG exports on pruned duplicate cluster nodes."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.layout.widgets.render import render_node_body
from figma_flutter_agent.parser.dedup import assign_structural_clusters, prune_duplicated_cluster_subtrees
from figma_flutter_agent.parser.render_boundary import resolve_pruned_cluster_instance_assets
from figma_flutter_agent.schemas import (
    AssetManifest,
    AssetManifestEntry,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
)


def _icon_rail(node_id: str, svg_id: str, vector_id: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Background",
        type=NodeType.ROW,
        sizing=Sizing(width=48.0, height=48.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=18.0),
        children=[
            CleanDesignTreeNode(
                id=svg_id,
                name="SVG",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id=vector_id,
                        name="Vector",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=20.0, height=20.0),
                    )
                ],
            )
        ],
    )


def test_resolve_pruned_cluster_instance_assets_uses_flattened_node_ids(
    tmp_path: Path,
) -> None:
    first = _icon_rail("281:100", "281:101", "281:102")
    second = _icon_rail("281:200", "281:201", "281:202")
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[first, second],
    )
    assign_structural_clusters(root)
    prune_duplicated_cluster_subtrees(root)

    asset_dir = tmp_path / "assets" / "icons"
    asset_dir.mkdir(parents=True)
    asset_path = asset_dir / "profile_contact_281_201.svg"
    asset_path.write_text("<svg></svg>", encoding="utf-8")

    manifest = AssetManifest(
        entries=[
            AssetManifestEntry(
                node_id="281:201",
                asset_path="assets/icons/profile_contact_281_201.svg",
                kind="icon",
            )
        ]
    )
    resolve_pruned_cluster_instance_assets(root, tmp_path, manifest)

    assert second.vector_asset_key == "assets/icons/profile_contact_281_201.svg"
    body = render_node_body(second, uses_svg=True, parent_type=NodeType.BUTTON)
    assert "SvgPicture.asset('assets/icons/profile_contact_281_201.svg'" in body


def test_resolve_pruned_cluster_instance_assets_prefers_instance_over_shared_cluster_asset(
    tmp_path: Path,
) -> None:
    first = _icon_rail("281:100", "281:101", "281:102")
    first.vector_asset_key = "assets/icons/profile_address_281_101.svg"
    second = _icon_rail("281:200", "281:201", "281:202")
    second.cluster_id = "cluster_0"
    second.vector_asset_key = "assets/icons/profile_address_281_101.svg"
    second.children = []
    second.flatten_figma_node_ids = ["281:201", "281:202"]
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[first, second],
    )

    asset_dir = tmp_path / "assets" / "icons"
    asset_dir.mkdir(parents=True)
    (asset_dir / "profile_contact_281_201.svg").write_text("<svg></svg>", encoding="utf-8")

    resolve_pruned_cluster_instance_assets(
        root,
        tmp_path,
        AssetManifest(
            entries=[
                AssetManifestEntry(
                    node_id="281:201",
                    asset_path="assets/icons/profile_contact_281_201.svg",
                    kind="icon",
                )
            ]
        ),
    )

    assert second.vector_asset_key == "assets/icons/profile_contact_281_201.svg"


def test_pruned_cluster_instance_skips_shared_cluster_widget_class() -> None:
    second = _icon_rail("281:200", "281:201", "281:202")
    second.cluster_id = "cluster_0"
    second.children = []
    second.flatten_figma_node_ids = ["281:201", "281:202"]
    second.vector_asset_key = "assets/icons/profile_contact_281_201.svg"
    body = render_node_body(
        second,
        uses_svg=True,
        parent_type=NodeType.BUTTON,
        cluster_classes={"cluster_0": "SvgWidget"},
    )
    assert "SvgWidget()" not in body
    assert "SvgPicture.asset('assets/icons/profile_contact_281_201.svg'" in body
