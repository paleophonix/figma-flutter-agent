"""Ownership diagnostic laws — report-only (05-P0-3)."""

from __future__ import annotations

from figma_flutter_agent.parser.layout.ownership import build_ownership_overlay
from figma_flutter_agent.parser.layout.reconcile_registry import list_reconcile_conflicts
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _node(node_id: str, node_type: NodeType, *, children: list | None = None) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=node_type,
        children=children or [],
    )


def test_ownership_card_surface_host_law() -> None:
    column = _node("col", NodeType.COLUMN)
    card = _node("card", NodeType.CARD)
    column.children = [card]
    overlay = build_ownership_overlay(column)
    assert any(edge.edge_type == "surface_host" for edge in overlay.edges)


def test_ownership_field_host_law() -> None:
    row = _node("row", NodeType.ROW)
    field = _node("field", NodeType.INPUT)
    row.children = [field]
    overlay = build_ownership_overlay(row)
    assert any(edge.edge_type == "field_host" for edge in overlay.edges)


def test_ownership_chrome_band_law() -> None:
    root = _node("root", NodeType.COLUMN)
    tabs = _node("tabs", NodeType.TABS)
    root.children = [tabs]
    overlay = build_ownership_overlay(root)
    assert any(edge.edge_type == "chrome_band" for edge in overlay.edges)


def test_ownership_icon_plate_law() -> None:
    row = _node("row", NodeType.ROW)
    icon = _node("icon_star", NodeType.VECTOR)
    row.children = [icon]
    overlay = build_ownership_overlay(row)
    assert any(edge.edge_type == "icon_plate" for edge in overlay.edges)


def test_reconcile_hero_conflict_visible() -> None:
    conflicts = list_reconcile_conflicts()
    assert ("reconcile_product_hero_photo_viewport_in_tree", "reconcile_stack_placements_in_tree") in conflicts
