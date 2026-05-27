import copy

from figma_flutter_agent.parser.dedup import (
    assign_structural_clusters,
    build_widget_extraction_hints,
    collect_component_instances,
    structural_signature,
)
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
)


def _card_node(node_id: str, *, text: str = "Title") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Product Card",
        type=NodeType.CARD,
        padding=Padding(top=8, bottom=8, left=8, right=8),
        spacing=4,
        sizing=Sizing(width_mode=SizingMode.FILL, height_mode=SizingMode.HUG),
        alignment=Alignment(main="start", cross="stretch"),
        style=NodeStyle(border_radius=8),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:text",
                name="Title",
                type=NodeType.TEXT,
                text=text,
            )
        ],
    )


def test_structural_signature_ignores_node_id() -> None:
    left = _card_node("1:1")
    right = _card_node("2:2")

    assert structural_signature(left) == structural_signature(right)


def test_assign_structural_clusters_groups_repeated_subtrees() -> None:
    cards = [_card_node(f"{index}:1") for index in range(5)]
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=cards,
    )

    summary = assign_structural_clusters(root)

    assert summary["cluster_0"] == 5
    assert all(card.cluster_id == "cluster_0" for card in cards)


def test_assign_structural_clusters_ignores_text_only_differences() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            _card_node("1:1", text="A"),
            _card_node("2:2", text="B"),
        ],
    )

    summary = assign_structural_clusters(root)

    assert summary["cluster_0"] == 2


def test_assign_structural_clusters_splits_different_structures() -> None:
    compact = _card_node("1:1")
    spacious = _card_node("2:2").model_copy(
        update={"padding": Padding(top=16, bottom=16, left=16, right=16)},
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[compact, spacious],
    )

    summary = assign_structural_clusters(root)

    assert summary == {}


def test_build_widget_extraction_hints_includes_components_and_clusters() -> None:
    dedup = collect_component_instances(
        {
            "id": "root",
            "type": "FRAME",
            "children": [
                {"id": "1:1", "type": "INSTANCE", "componentId": "comp_a", "visible": True},
                {"id": "2:2", "type": "INSTANCE", "componentId": "comp_a", "visible": True},
            ],
        }
    )
    hints = build_widget_extraction_hints(dedup, {"cluster_0": 4})

    assert any("comp_a" in hint for hint in hints)
    assert any("cluster_0" in hint for hint in hints)


def test_build_clean_tree_returns_cluster_summary() -> None:
    card_template = {
        "type": "FRAME",
        "name": "Product Card",
        "layoutMode": "VERTICAL",
        "paddingTop": 8,
        "paddingBottom": 8,
        "paddingLeft": 8,
        "paddingRight": 8,
        "itemSpacing": 4,
        "cornerRadius": 8,
        "children": [
            {
                "id": "text",
                "type": "TEXT",
                "name": "Title",
                "characters": "Title",
                "style": {"fontSize": 16},
            }
        ],
    }
    root = {
        "id": "0:1",
        "name": "Screen",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "children": [copy.deepcopy({**card_template, "id": f"{index}:1"}) for index in range(3)],
    }

    tree, ratio, dedup, cluster_summary = build_clean_tree(root)

    assert tree.type == NodeType.COLUMN
    assert ratio == 0.0
    assert dedup.instance_count == {}
    assert cluster_summary["cluster_0"] == 3
