"""Asset node index for plan-stage paths (04-P0-5)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.parser.tree_walk import walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode


@dataclass(frozen=True, slots=True)
class AssetNodeIndex:
    """Index of asset keys by clean-tree node id."""

    vector_by_node: dict[str, str]
    image_by_node: dict[str, str]

    def vector_for(self, node_id: str) -> str | None:
        return self.vector_by_node.get(node_id)

    def image_for(self, node_id: str) -> str | None:
        return self.image_by_node.get(node_id)


def build_asset_node_index(root: CleanDesignTreeNode) -> AssetNodeIndex:
    """Build asset index via single cycle-safe walk (no per-node glob)."""
    vector_by_node: dict[str, str] = {}
    image_by_node: dict[str, str] = {}

    def visitor(node: CleanDesignTreeNode) -> None:
        if node.vector_asset_key:
            vector_by_node[node.id] = node.vector_asset_key
        if node.image_asset_key:
            image_by_node[node.id] = node.image_asset_key

    walk_clean_tree(root, visitor, phase="asset_index")
    return AssetNodeIndex(vector_by_node=vector_by_node, image_by_node=image_by_node)
