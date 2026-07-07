"""Regression tests for LAW-CLUSTER-PRUNE-PAINT-CONSERVATION."""

from copy import deepcopy

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    conservation_node_multiset,
)
from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def _plus_icon_stack(*, node_id: str, vector_id: str) -> CleanDesignTreeNode:
    """Generic duplicated 28px plus icon component (no exported SVG)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="Icons/28/Plus",
        type=NodeType.STACK,
        cluster_id="component_icons_28_plus",
        component_ref="910:3249",
        sizing=Sizing(width=28.0, height=28.0),
        children=[
            CleanDesignTreeNode(
                id=vector_id,
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=14.0, height=14.0),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )


def test_duplicate_plus_icon_keeps_children_without_vector_asset() -> None:
    """Law: cluster prune must not drop unbound visible vector paint."""
    first = _plus_icon_stack(node_id="plus-1", vector_id="vec-1")
    duplicate = _plus_icon_stack(node_id="plus-2", vector_id="vec-2")
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[first, duplicate],
    )
    prune_generation_layout_tree(root, checkpoint=None)

    assert first.children
    assert duplicate.children
    assert duplicate.children[0].type == NodeType.VECTOR
    assert duplicate.children[0].vector_asset_key is None


def test_duplicate_plus_icon_cp0_parse_preserves_multiset_and_inline_paint() -> None:
    """Blocked prune must not assign flatten metadata while children remain."""
    first = _plus_icon_stack(node_id="plus-1", vector_id="vec-1")
    duplicate = _plus_icon_stack(node_id="plus-2", vector_id="vec-2")
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[first, duplicate],
    )
    before = conservation_node_multiset(deepcopy(root))
    prune_generation_layout_tree(root, checkpoint="CP0_parse")
    after = conservation_node_multiset(root)

    assert before == after
    assert duplicate.children
    assert not duplicate.flatten_figma_node_ids


def test_duplicate_plus_icon_forwards_vector_asset_when_template_bound() -> None:
    """Prune may clear children when drawable vector asset transfers to the cluster root."""
    glyph = CleanDesignTreeNode(
        id="vec-rich",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/plus.svg",
        sizing=Sizing(width=14.0, height=14.0),
    )
    template = CleanDesignTreeNode(
        id="plus-rich",
        name="Icons/28/Plus",
        type=NodeType.STACK,
        cluster_id="component_icons_28_plus",
        component_ref="910:3249",
        sizing=Sizing(width=28.0, height=28.0),
        children=[glyph],
    )
    duplicate = CleanDesignTreeNode(
        id="plus-dup",
        name="Icons/28/Plus",
        type=NodeType.STACK,
        cluster_id="component_icons_28_plus",
        component_ref="910:3249",
        sizing=Sizing(width=28.0, height=28.0),
        children=[
            CleanDesignTreeNode(
                id="vec-dup",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=14.0, height=14.0),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[template, duplicate],
    )
    prune_generation_layout_tree(root, checkpoint=None)

    assert duplicate.vector_asset_key == "assets/icons/plus.svg"
    assert duplicate.children == []


def test_late_image_asset_does_not_unlock_prune_when_child_vectors_remain() -> None:
    """Raster on the cluster root must not clear inline VECTOR children (CP0b idempotency)."""
    vector = CleanDesignTreeNode(
        id="vec-rich",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=14.0, height=14.0),
        style=NodeStyle(background_color="0xFFFFFFFF"),
    )
    template = CleanDesignTreeNode(
        id="cutlery-1",
        name="Cutlery",
        type=NodeType.COLUMN,
        cluster_id="component_cutlery",
        sizing=Sizing(width=375.0, height=76.0),
        children=[
            CleanDesignTreeNode(
                id="body-1",
                name="Body",
                type=NodeType.STACK,
                children=[vector],
            )
        ],
    )
    duplicate = CleanDesignTreeNode(
        id="cutlery-2",
        name="Cutlery",
        type=NodeType.COLUMN,
        cluster_id="component_cutlery",
        image_asset_key="assets/images/tableware.png",
        sizing=Sizing(width=375.0, height=76.0),
        children=[
            CleanDesignTreeNode(
                id="body-2",
                name="Body",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id="vec-dup",
                        name="Vector",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=14.0, height=14.0),
                        style=NodeStyle(background_color="0xFFFFFFFF"),
                    )
                ],
            )
        ],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[template, duplicate],
    )
    before = conservation_node_multiset(deepcopy(root))
    prune_generation_layout_tree(root, checkpoint="CP0b_reprune")
    after = conservation_node_multiset(root)

    assert before == after
    assert duplicate.children
    assert duplicate.children[0].children
