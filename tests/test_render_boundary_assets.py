"""Render-boundary asset resolution for offline dump / local manifest."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.parser.boundaries.assets import (
    discover_asset_path_for_node,
    render_boundary_asset_path,
    resolve_discovered_vector_asset_keys,
    resolve_render_boundary_asset_keys,
)
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.schemas import (
    AssetManifest,
    AssetManifestEntry,
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_discover_asset_path_for_node(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    target = icons / "group_6813_1_3665.svg"
    target.write_text("<svg></svg>", encoding="utf-8")
    assert discover_asset_path_for_node(tmp_path, "1:3665") == "assets/icons/group_6813_1_3665.svg"


def test_discover_asset_path_for_instance_leaf_id(tmp_path: Path) -> None:
    """Canonical exports (910:3248) resolve for nested instance vector ids."""
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "vector_910_3248.svg").write_text("<svg></svg>", encoding="utf-8")
    instance_id = "I4408:44896;1154:7849;1149:9855;1149:9481;910:3248"
    assert (
        discover_asset_path_for_node(tmp_path, instance_id) == "assets/icons/vector_910_3248.svg"
    )


def test_discover_asset_path_for_component_vector_family_variant(tmp_path: Path) -> None:
    """Sibling variant vectors in one Figma file share a file-key export family."""
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "vector_1162_10106.svg").write_text("<svg></svg>", encoding="utf-8")
    variant_id = "I3561:42994;1406:12001;1162:10248"
    assert (
        discover_asset_path_for_node(tmp_path, variant_id) == "assets/icons/vector_1162_10106.svg"
    )


def test_resolve_discovered_vector_asset_keys_binds_component_vector_family(
    tmp_path: Path,
) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "vector_1162_10106.svg").write_text("<svg></svg>", encoding="utf-8")
    vector = CleanDesignTreeNode(
        id="I3561:42994;1406:12001;1162:10248",
        name="Vector",
        type=NodeType.VECTOR,
        component_ref="3481:34993",
        sizing=Sizing(width=28.0, height=28.0),
    )
    resolve_discovered_vector_asset_keys(vector, tmp_path)
    assert vector.vector_asset_key == "assets/icons/vector_1162_10106.svg"


def test_resolve_discovered_vector_asset_keys_attaches_export(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "google_I28_4028;3_6131.svg").write_text("<svg></svg>", encoding="utf-8")
    stack = CleanDesignTreeNode(
        id="I28:4028;3:6131",
        name="google",
        type=NodeType.STACK,
        sizing=Sizing(width=20.0, height=20.0),
        children=[
            CleanDesignTreeNode(
                id="I28:4028;3:6131;136:155",
                name="vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=8.0, height=8.0),
            ),
            CleanDesignTreeNode(
                id="I28:4028;3:6131;136:156",
                name="vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=8.0, height=8.0),
            ),
        ],
    )
    resolve_discovered_vector_asset_keys(stack, tmp_path)
    assert stack.vector_asset_key == "assets/icons/google_I28_4028;3_6131.svg"


def test_resolve_render_boundary_uses_discovered_file(tmp_path: Path) -> None:
    illustrations = tmp_path / "assets" / "illustrations"
    illustrations.mkdir(parents=True)
    (illustrations / "hero_1_3665.svg").write_text("<svg></svg>", encoding="utf-8")
    node = CleanDesignTreeNode(
        id="1:3665",
        name="Hero",
        type=NodeType.STACK,
        render_boundary=True,
        vector_asset_key=render_boundary_asset_path("1:3665"),
        stack_placement=StackPlacement(left=0, top=0, width=100, height=100),
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=100,
            height=100,
        ),
        children=[],
    )
    root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[node])
    unresolved = resolve_render_boundary_asset_keys(root, tmp_path, AssetManifest())
    assert unresolved == []
    assert node.vector_asset_key == "assets/illustrations/hero_1_3665.svg"


def test_local_manifest_includes_illustration_svg(tmp_path: Path) -> None:
    illustrations = tmp_path / "assets" / "illustrations"
    illustrations.mkdir(parents=True)
    (illustrations / "mask_group_3_3.svg").write_text("<svg></svg>", encoding="utf-8")
    manifest = local_asset_manifest_from_project(tmp_path)
    paths = {entry.asset_path for entry in manifest.entries}
    assert "assets/illustrations/mask_group_3_3.svg" in paths


def test_resolve_prefers_manifest_entry(tmp_path: Path) -> None:
    illustrations = tmp_path / "assets" / "illustrations"
    illustrations.mkdir(parents=True)
    path = illustrations / "group_1_3665.svg"
    path.write_text("<svg></svg>", encoding="utf-8")
    manifest = AssetManifest(
        entries=[
            AssetManifestEntry(
                node_id="1:3665",
                asset_path="assets/illustrations/group_1_3665.svg",
                kind="illustration",
            )
        ]
    )
    node = CleanDesignTreeNode(
        id="1:3665",
        name="Group",
        type=NodeType.STACK,
        render_boundary=True,
        vector_asset_key=render_boundary_asset_path("1:3665"),
        children=[],
    )
    root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[node])
    assert resolve_render_boundary_asset_keys(root, tmp_path, manifest) == []
    assert node.vector_asset_key == "assets/illustrations/group_1_3665.svg"


def _render_boundary_node(node_id: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Pattern",
        type=NodeType.STACK,
        render_boundary=True,
        vector_asset_key=render_boundary_asset_path(node_id),
        image_asset_key="assets/images/render_boundary_placeholder.png",
        stack_placement=StackPlacement(left=0, top=0, width=375, height=257),
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=375,
            height=257,
        ),
        children=[],
    )


def test_unresolved_render_boundary_clears_asset_keys_when_non_strict(tmp_path: Path) -> None:
    node = _render_boundary_node("42:2283")
    root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[node])
    unresolved = resolve_render_boundary_asset_keys(root, tmp_path, AssetManifest(), strict=False)
    assert unresolved == ["42:2283"]
    assert node.vector_asset_key is None
    assert node.image_asset_key is None


def test_unresolved_render_boundary_validate_passes_after_non_strict_resolve(
    tmp_path: Path,
) -> None:
    node = _render_boundary_node("42:2283")
    root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[node])
    resolve_render_boundary_asset_keys(root, tmp_path, AssetManifest(), strict=False)
    screen_ir = default_screen_ir(root)
    validate_screen_ir(screen_ir, root, project_dir=tmp_path)


def test_resolve_render_boundary_binds_raster_export(tmp_path: Path) -> None:
  illustrations = tmp_path / "assets" / "illustrations"
  illustrations.mkdir(parents=True)
  (illustrations / "render_boundary_2399_42779.png").write_bytes(b"png")
  node = CleanDesignTreeNode(
      id="2399:42779",
      name="Img",
      type=NodeType.STACK,
      sizing=Sizing(width=393.0, height=454.0),
      render_boundary=True,
      flatten_figma_node_ids=["2399:42780", "2399:42781"],
      vector_asset_key=render_boundary_asset_path("2399:42779"),
  )
  root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[node])
  unresolved = resolve_render_boundary_asset_keys(root, tmp_path, AssetManifest())
  assert unresolved == []
  assert node.image_asset_key == "assets/illustrations/render_boundary_2399_42779.png"


def test_unresolved_render_boundary_strict_raises(tmp_path: Path) -> None:
    node = _render_boundary_node("1:boundary")
    root = CleanDesignTreeNode(id="screen", name="Screen", type=NodeType.STACK, children=[node])
    with pytest.raises(GenerationError, match="Render-boundary asset"):
        resolve_render_boundary_asset_keys(root, tmp_path, AssetManifest(), strict=True)
    assert node.vector_asset_key == render_boundary_asset_path("1:boundary")
