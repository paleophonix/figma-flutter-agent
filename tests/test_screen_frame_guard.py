"""Tests for screen-frame asset guardrails."""

from pathlib import Path

from figma_flutter_agent.assets.collect import collect_exportable_nodes
from figma_flutter_agent.assets.screen_frame import (
    build_screen_frame_exclude_ids,
    filter_manifest,
    prune_screen_frame_assets,
    sanitize_dart_blocked_assets,
    strip_screen_frame_assets_from_tree,
)
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.schemas import (
    AssetManifest,
    AssetManifestEntry,
    CleanDesignTreeNode,
    NodeType,
)
from figma_flutter_agent.stages.assets import finalize_screen_assets


def test_collect_exportable_nodes_skips_excluded_screen_frame() -> None:
    root = {
        "id": "1:3661",
        "name": "sign up and Sign in",
        "type": "FRAME",
        "visible": True,
        "exportSettings": [{"format": "PNG"}],
        "children": [
            {
                "id": "1:3663",
                "name": "Vector",
                "type": "VECTOR",
                "visible": True,
            }
        ],
    }
    exclude = build_screen_frame_exclude_ids("1:3661", {"1:4000"})
    items = collect_exportable_nodes(root, exclude_node_ids=set(exclude))
    node_ids = {node_id for node_id, _, _ in items}
    assert "1:3661" not in node_ids
    assert "1:3663" in node_ids


def test_local_asset_manifest_excludes_screen_frame_files(tmp_path: Path) -> None:
    icons_dir = tmp_path / "assets" / "icons"
    icons_dir.mkdir(parents=True)
    (icons_dir / "sign_up_and_sign_in_1_3661.svg").write_text("<svg/>", encoding="utf-8")
    (icons_dir / "vector_1_3663.svg").write_text("<svg/>", encoding="utf-8")

    exclude = build_screen_frame_exclude_ids("1:3661", set())
    manifest = local_asset_manifest_from_project(tmp_path, exclude_node_ids=exclude)

    assert {entry.node_id for entry in manifest.entries} == {"1:3663"}


def test_finalize_screen_assets_strips_root_and_prunes_file(tmp_path: Path) -> None:
    icons_dir = tmp_path / "assets" / "icons"
    icons_dir.mkdir(parents=True)
    stale = icons_dir / "sign_up_and_sign_in_1_3661.svg"
    stale.write_text("<svg/>", encoding="utf-8")

    tree = CleanDesignTreeNode(id="1:3661", name="Screen", type=NodeType.STACK)
    manifest = AssetManifest(
        entries=[
            AssetManifestEntry(
                node_id="1:3661",
                asset_path="assets/icons/sign_up_and_sign_in_1_3661.svg",
                kind="icon",
            )
        ]
    )

    filtered, blocked = finalize_screen_assets(
        project_dir=tmp_path,
        clean_tree=tree,
        destination_trees={},
        manifest=manifest,
        primary_node_id="1:3661",
        destination_node_ids=set(),
    )

    assert filtered.entries == []
    assert not stale.exists()
    assert tree.vector_asset_key is None
    assert "assets/icons/sign_up_and_sign_in_1_3661.svg" in blocked


def test_sanitize_dart_blocked_assets_removes_fullscreen_background() -> None:
    source = """
return Stack(
  children: [
    Positioned.fill(
      child: SvgPicture.asset(
        'assets/icons/sign_up_and_sign_in_1_3661.svg',
        fit: BoxFit.cover,
      ),
    ),
    const Text('SIGN UP'),
  ],
);
"""
    blocked = frozenset({"assets/icons/sign_up_and_sign_in_1_3661.svg"})
    sanitized = sanitize_dart_blocked_assets(source, blocked)
    assert "sign_up_and_sign_in_1_3661.svg" not in sanitized
    assert "SIGN UP" in sanitized


def test_strip_screen_frame_assets_from_tree_clears_root_keys() -> None:
    tree = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        vector_asset_key="assets/icons/sign_up_and_sign_in_1_3661.svg",
        children=[
            CleanDesignTreeNode(
                id="1:3663",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_1_3663.svg",
            )
        ],
    )
    strip_screen_frame_assets_from_tree(tree, build_screen_frame_exclude_ids("1:3661", set()))
    assert tree.vector_asset_key is None
    assert tree.children[0].vector_asset_key == "assets/icons/vector_1_3663.svg"


def test_filter_manifest_drops_excluded_entries() -> None:
    manifest = AssetManifest(
        entries=[
            AssetManifestEntry(node_id="1:3661", asset_path="assets/icons/a.svg", kind="icon"),
            AssetManifestEntry(node_id="1:2", asset_path="assets/icons/b.svg", kind="icon"),
        ]
    )
    filtered = filter_manifest(manifest, build_screen_frame_exclude_ids("1:3661", set()))
    assert [entry.node_id for entry in filtered.entries] == ["1:2"]


def test_prune_screen_frame_assets_deletes_matching_files(tmp_path: Path) -> None:
    icons_dir = tmp_path / "assets" / "icons"
    icons_dir.mkdir(parents=True)
    keep = icons_dir / "vector_1_3663.svg"
    remove = icons_dir / "screen_1_3661.svg"
    keep.write_text("<svg/>", encoding="utf-8")
    remove.write_text("<svg/>", encoding="utf-8")

    removed = prune_screen_frame_assets(tmp_path, build_screen_frame_exclude_ids("1:3661", set()))
    assert remove.as_posix() in removed
    assert keep.exists()
