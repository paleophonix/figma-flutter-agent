"""Tests for cluster-pruned CARD hydration during dedup."""

from figma_flutter_agent.parser.dedup.hydrate import (
    _should_hydrate_pruned_instance,
    hydrate_pruned_cluster_instances,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


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


def test_should_hydrate_cluster_pruned_stack_without_flatten() -> None:
    pruned = CleanDesignTreeNode(
        id="icon-dup",
        name="Icon Salary",
        type=NodeType.STACK,
        cluster_id="component_7102_2848",
        component_ref="7102:2848",
        sizing=Sizing(width=57.0, height=53.0),
        children=[],
    )
    assert _should_hydrate_pruned_instance(pruned) is True


def test_should_not_hydrate_skip_control_sized_asset_stub() -> None:
    """Playback-sized skip controls must stay pruned asset stubs, not rehydrate."""
    pruned = CleanDesignTreeNode(
        id="skip-pruned",
        name="Skip",
        type=NodeType.STACK,
        cluster_id="component_skip_15",
        vector_asset_key="assets/icons/vector_skip.svg",
        sizing=Sizing(width=40.0, height=40.0),
        children=[],
    )
    assert _should_hydrate_pruned_instance(pruned) is False


def test_hydrate_restores_component_stack_duplicate_without_flatten() -> None:
    substrate = CleanDesignTreeNode(
        id="rect",
        name="Rectangle 150",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=57.0, height=53.0),
        style=NodeStyle(background_color="0xFF6DB6FE", border_radius=22.0),
    )
    glyph = CleanDesignTreeNode(
        id="vec",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/vector_salary.svg",
        sizing=Sizing(width=26.0, height=23.5),
    )
    template = CleanDesignTreeNode(
        id="icon-rich",
        name="Icon Salary",
        type=NodeType.STACK,
        cluster_id="component_7102_2848",
        component_ref="7102:2848",
        sizing=Sizing(width=57.0, height=53.0),
        children=[substrate, glyph],
    )
    pruned = CleanDesignTreeNode(
        id="icon-dup",
        name="Icon Salary",
        type=NodeType.STACK,
        cluster_id="component_7102_2848",
        component_ref="7102:2848",
        sizing=Sizing(width=57.0, height=53.0),
        children=[],
    )
    root = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        children=[template, pruned],
    )
    hydrate_pruned_cluster_instances(root)
    assert len(pruned.children) == 2
