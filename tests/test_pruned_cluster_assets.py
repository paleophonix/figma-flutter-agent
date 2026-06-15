"""Resolve per-instance SVG exports on pruned duplicate cluster nodes."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.widget_extractor import (
    collect_cluster_widget_specs,
    render_cluster_widgets,
)
from figma_flutter_agent.parser.boundaries.assets import (
    resolve_discovered_vector_asset_keys,
    resolve_pruned_cluster_instance_assets,
)
from figma_flutter_agent.parser.dedup.clusters import assign_structural_clusters
from figma_flutter_agent.parser.dedup.prune import prune_duplicated_cluster_subtrees
from figma_flutter_agent.schemas import (
    AssetManifest,
    AssetManifestEntry,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
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


def test_pruned_star_cluster_binds_vector_asset_key(tmp_path: Path) -> None:
    star_vector = CleanDesignTreeNode(
        id="211:5818",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=18.0, height=18.0),
    )
    star_instance = CleanDesignTreeNode(
        id="259:6571",
        name="StarFilled",
        type=NodeType.STACK,
        sizing=Sizing(width=20.0, height=20.0),
        children=[star_vector],
    )
    first = CleanDesignTreeNode(
        id="281:100",
        name="StarFilled",
        type=NodeType.STACK,
        cluster_id="cluster_star",
        sizing=Sizing(width=20.0, height=20.0),
        children=[star_instance],
    )
    second = CleanDesignTreeNode(
        id="281:200",
        name="StarFilled",
        type=NodeType.STACK,
        cluster_id="cluster_star",
        sizing=Sizing(width=20.0, height=20.0),
        children=[],
        flatten_figma_node_ids=["259:6571", "211:5818"],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.ROW,
        children=[first, second],
    )
    assign_structural_clusters(root)
    prune_duplicated_cluster_subtrees(root)

    asset_dir = tmp_path / "assets" / "icons"
    asset_dir.mkdir(parents=True)
    (asset_dir / "star_filled_259_6571.svg").write_text("<svg></svg>", encoding="utf-8")

    resolve_pruned_cluster_instance_assets(
        root,
        tmp_path,
        AssetManifest(
            entries=[
                AssetManifestEntry(
                    node_id="259:6571",
                    asset_path="assets/icons/star_filled_259_6571.svg",
                    kind="icon",
                )
            ]
        ),
    )

    assert second.vector_asset_key == "assets/icons/star_filled_259_6571.svg"
    body = render_node_body(second, uses_svg=True, parent_type=NodeType.ROW)
    assert "SvgPicture.asset('assets/icons/star_filled_259_6571.svg'" in body
    assert "SizedBox.shrink()" not in body


def test_resolve_discovered_vector_asset_keys_finds_composite_parent_id(
    tmp_path: Path,
) -> None:
    star_vector = CleanDesignTreeNode(
        id="211:5818",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=18.0, height=18.0),
    )
    star_icon = CleanDesignTreeNode(
        id="259:6571",
        name="StarFilled",
        type=NodeType.STACK,
        sizing=Sizing(width=20.0, height=20.0),
        children=[star_vector],
    )
    representative = CleanDesignTreeNode(
        id="281:7386",
        name="StarFilled",
        type=NodeType.STACK,
        cluster_id="cluster_star",
        sizing=Sizing(width=20.0, height=20.0),
        children=[star_icon],
    )
    asset_dir = tmp_path / "assets" / "icons"
    asset_dir.mkdir(parents=True)
    (asset_dir / "star_filled_259_6571.svg").write_text("<svg></svg>", encoding="utf-8")

    resolve_discovered_vector_asset_keys(representative, tmp_path)

    assert representative.vector_asset_key == "assets/icons/star_filled_259_6571.svg"


def test_cluster_representative_emits_svg_picture_widget(tmp_path: Path) -> None:
    star_vector = CleanDesignTreeNode(
        id="211:5818",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=18.0, height=18.0),
    )
    star_icon = CleanDesignTreeNode(
        id="259:6571",
        name="StarFilled",
        type=NodeType.STACK,
        sizing=Sizing(width=20.0, height=20.0),
        children=[star_vector],
    )
    first = CleanDesignTreeNode(
        id="281:100",
        name="StarFilled",
        type=NodeType.STACK,
        cluster_id="cluster_star",
        sizing=Sizing(width=20.0, height=20.0),
        children=[star_icon],
    )
    second = CleanDesignTreeNode(
        id="281:200",
        name="StarFilled",
        type=NodeType.STACK,
        cluster_id="cluster_star",
        sizing=Sizing(width=20.0, height=20.0),
        children=[],
        flatten_figma_node_ids=["259:6571", "211:5818"],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.ROW,
        children=[first, second],
    )
    asset_dir = tmp_path / "assets" / "icons"
    asset_dir.mkdir(parents=True)
    (asset_dir / "star_filled_259_6571.svg").write_text("<svg></svg>", encoding="utf-8")

    specs = collect_cluster_widget_specs(screen, {"cluster_star": 2})
    result = render_cluster_widgets(
        specs,
        uses_svg=True,
        clean_trees=[screen],
        project_dir=tmp_path,
    )
    widget_source = next(iter(result.files.values()))

    assert "SvgPicture.asset('assets/icons/star_filled_259_6571.svg'" in widget_source
    assert "BoxDecoration" not in widget_source
    assert "SizedBox.shrink()" not in widget_source


def test_resolve_discovered_vector_asset_keys_binds_compact_icon_button(
    tmp_path: Path,
) -> None:
    vector = CleanDesignTreeNode(
        id="I281:7245;164:2038;109:1874",
        name="Shape",
        type=NodeType.VECTOR,
        sizing=Sizing(width=11.7, height=19.2),
        style=NodeStyle(background_color="0xFF006FFD"),
    )
    fill = CleanDesignTreeNode(
        id="I281:7245;164:2038;109:1922",
        name="Fill",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=20.0, height=20.0),
        style=NodeStyle(background_color="0xFF006FFD"),
    )
    back_button = CleanDesignTreeNode(
        id="I281:7245;164:2038",
        name="Left Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=20.0, height=20.0),
        children=[vector, fill],
    )
    asset_dir = tmp_path / "assets" / "icons"
    asset_dir.mkdir(parents=True)
    (asset_dir / "left_button_I281_7245;164_2038.svg").write_text("<svg></svg>", encoding="utf-8")

    resolve_discovered_vector_asset_keys(back_button, tmp_path)

    assert back_button.vector_asset_key == "assets/icons/left_button_I281_7245;164_2038.svg"
    body = render_node_body(back_button, uses_svg=True, parent_type=NodeType.STACK)
    assert "SvgPicture.asset('assets/icons/left_button_I281_7245;164_2038.svg'" in body
    assert "Ink(decoration: BoxDecoration(color: Color(0xFF006FFD))" not in body
