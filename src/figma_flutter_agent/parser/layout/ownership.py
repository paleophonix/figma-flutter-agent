"""Visual ownership overlay — report-only sidecar (Program 05 P0-1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

OwnershipEdgeType = Literal[
    "surface_host",
    "icon_plate",
    "chrome_band",
    "field_host",
    "scroll_chrome",
]


@dataclass(frozen=True, slots=True)
class OwnershipEdge:
    """Directed ownership edge between clean-tree nodes."""

    edge_type: OwnershipEdgeType
    owner_id: str
    child_id: str
    provenance: str


@dataclass(frozen=True, slots=True)
class OwnershipOverlay:
    """Sidecar ownership graph — does not mutate layout intent."""

    edges: tuple[OwnershipEdge, ...]


def _infer_edge(node: CleanDesignTreeNode, parent: CleanDesignTreeNode | None) -> OwnershipEdge | None:
    if parent is None:
        return None
    if node.type == NodeType.INPUT:
        return OwnershipEdge(
            edge_type="field_host",
            owner_id=parent.id,
            child_id=node.id,
            provenance="ownership_pass_p0",
        )
    if node.type in {NodeType.BOTTOM_NAV, NodeType.TABS}:
        return OwnershipEdge(
            edge_type="chrome_band",
            owner_id=node.id,
            child_id=parent.id,
            provenance="ownership_pass_p0",
        )
    if node.type == NodeType.CARD and parent.type == NodeType.COLUMN:
        return OwnershipEdge(
            edge_type="surface_host",
            owner_id=node.id,
            child_id=parent.id,
            provenance="ownership_pass_p0",
        )
    name_lower = (node.name or "").lower()
    if "icon" in name_lower and parent is not None:
        return OwnershipEdge(
            edge_type="icon_plate",
            owner_id=parent.id,
            child_id=node.id,
            provenance="ownership_pass_p0",
        )
    return None


def build_ownership_overlay(root: CleanDesignTreeNode) -> OwnershipOverlay:
    """Build report-only ownership edges without mutating the clean tree."""
    edges: list[OwnershipEdge] = []

    def visitor(node: CleanDesignTreeNode, parent: CleanDesignTreeNode | None) -> None:
        edge = _infer_edge(node, parent)
        if edge is not None:
            edges.append(edge)

    from figma_flutter_agent.parser.tree_walk import walk_clean_tree_with_parent

    walk_clean_tree_with_parent(root, visitor, phase="ownership_overlay")
    return OwnershipOverlay(edges=tuple(edges))


def ownership_overlay_to_json(overlay: OwnershipOverlay) -> list[dict[str, str]]:
    """Serialize overlay for ``ownership_overlay.json`` debug artifact."""
    return [
        {
            "edge_type": edge.edge_type,
            "owner_id": edge.owner_id,
            "child_id": edge.child_id,
            "provenance": edge.provenance,
        }
        for edge in overlay.edges
    ]
