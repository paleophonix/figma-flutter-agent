"""Tests for cluster-pruned CARD hydration during dedup."""

from figma_flutter_agent.parser.dedup.hydrate import (
    _should_hydrate_pruned_instance,
    hydrate_pruned_cluster_instances,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_pruned_card_with_flatten_ids_should_hydrate() -> None:
    card = CleanDesignTreeNode(
        id="card-pruned",
        name="Image Card",
        type=NodeType.CARD,
        cluster_id="component_348_22_abc",
        vector_asset_key="assets/images/stub.png",
        flatten_figma_node_ids=["figma-a", "figma-b"],
        sizing=Sizing(width=168.0, height=296.0),
        children=[],
    )
    assert _should_hydrate_pruned_instance(card) is True


def test_hydrate_restores_card_children_from_richest_template() -> None:
    hero = CleanDesignTreeNode(
        id="hero",
        name="image",
        type=NodeType.STACK,
        sizing=Sizing(width=152.0, height=152.0),
        children=[
            CleanDesignTreeNode(
                id="img",
                name="image",
                type=NodeType.IMAGE,
                image_asset_key="assets/images/hero.png",
                sizing=Sizing(width=152.0, height=152.0),
            )
        ],
    )
    meta = CleanDesignTreeNode(
        id="meta",
        name="copy",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Header",
                type=NodeType.TEXT,
                text="Header",
            )
        ],
    )
    template = CleanDesignTreeNode(
        id="card-rich",
        name="Image Card",
        type=NodeType.CARD,
        cluster_id="component_348_22_abc",
        sizing=Sizing(width=168.0, height=296.0),
        children=[hero, meta],
    )
    pruned = CleanDesignTreeNode(
        id="card-pruned",
        name="Image Card",
        type=NodeType.CARD,
        cluster_id="component_348_22_abc",
        vector_asset_key="assets/images/stub.png",
        flatten_figma_node_ids=["figma-a"],
        sizing=Sizing(width=168.0, height=296.0),
        children=[],
    )
    root = CleanDesignTreeNode(
        id="row",
        name="scroll_frame",
        type=NodeType.ROW,
        children=[template, pruned],
    )
    hydrate_pruned_cluster_instances(root)
    assert len(pruned.children) == 2
    assert pruned.vector_asset_key is None
