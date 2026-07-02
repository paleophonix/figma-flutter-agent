"""Planner normalize asset-index and tree-walk termination laws."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.boundaries.assets import resolve_missing_image_asset_keys
from figma_flutter_agent.parser.tree_walk import CleanTreeCycleError, walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_normalize_clean_tree_uses_asset_index_not_per_node_glob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AssetIndexReuseLaw: one iterdir scan; no per-node Path.glob during normalize."""
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "photo_9_9.svg").write_text("<svg/>", encoding="utf-8")

    def forbidden_glob(self: Path, pattern: str) -> object:
        msg = f"Path.glob must not run during normalize asset resolve (pattern={pattern!r})"
        raise AssertionError(msg)

    monkeypatch.setattr(Path, "glob", forbidden_glob)

    leaf = CleanDesignTreeNode(
        id="9:9",
        name="Photo",
        type=NodeType.IMAGE,
        sizing=Sizing(width=48.0, height=48.0),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[leaf],
    )

    normalized = normalize_clean_tree(
        root,
        project_dir=tmp_path,
        apply_render_safety=False,
        use_geometry_planner=False,
        archetype_reconcile=False,
    )
    photo = normalized.children[0]
    assert photo.image_asset_key == "assets/icons/photo_9_9.svg"


def test_clean_tree_cycle_raises_clean_tree_cycle_error() -> None:
    """TreeTraversalTerminationLaw: object-identity cycles fail loud, not hang."""
    node_a = CleanDesignTreeNode(id="a", name="A", type=NodeType.COLUMN, children=[])
    node_b = CleanDesignTreeNode(id="b", name="B", type=NodeType.COLUMN, children=[])
    node_a.children = [node_b]
    node_b.children = [node_a]

    with pytest.raises(CleanTreeCycleError):
        walk_clean_tree(node_a, lambda _node: None)


def test_resolve_missing_image_asset_keys_raises_on_cycle(tmp_path: Path) -> None:
    """Asset walks share the same cycle guard as generic tree walks."""
    node_a = CleanDesignTreeNode(id="a", name="A", type=NodeType.IMAGE, children=[])
    node_b = CleanDesignTreeNode(id="b", name="B", type=NodeType.COLUMN, children=[])
    node_a.children = [node_b]
    node_b.children = [node_a]

    with pytest.raises(CleanTreeCycleError):
        resolve_missing_image_asset_keys(node_a, tmp_path, asset_index={})
