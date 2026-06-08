import pytest

from figma_flutter_agent.parser.tree_node import extract_style, infer_leaf_type
from figma_flutter_agent.schemas import NodeType


@pytest.mark.parametrize(
    ("node", "expected"),
    [
        ({"type": "TEXT", "name": "Title"}, NodeType.TEXT),
        ({"type": "VECTOR", "name": "Icon"}, NodeType.VECTOR),
        ({"type": "VECTOR", "name": "Google button shadow"}, NodeType.VECTOR),
        ({"type": "BOOLEAN_OPERATION", "name": "card outline"}, NodeType.VECTOR),
        (
            {
                "type": "RECTANGLE",
                "name": "Photo",
                "fills": [{"type": "IMAGE"}],
            },
            NodeType.IMAGE,
        ),
        ({"type": "FRAME", "name": "Email Input"}, NodeType.INPUT),
        ({"type": "FRAME", "name": "Primary Button"}, NodeType.BUTTON),
        ({"type": "INSTANCE", "name": "Submit btn"}, NodeType.BUTTON),
        ({"type": "INSTANCE", "name": "Submit"}, NodeType.CONTAINER),
        ({"type": "FRAME", "name": "Product Card"}, NodeType.CARD),
    ],
)
def test_infer_leaf_type(node: dict[str, object], expected: NodeType) -> None:
    assert infer_leaf_type(node) == expected


def test_infer_leaf_type_uses_components_api_for_instances() -> None:
    assert (
        infer_leaf_type(
            {"type": "INSTANCE", "name": "Submit", "componentId": "comp-1"},
            components={"comp-1": {"name": "Button/Primary"}},
        )
        == NodeType.BUTTON
    )


def test_build_clean_tree_maps_overlay_frame_without_modal_in_name() -> None:
    from figma_flutter_agent.parser.tree import build_clean_tree

    root = {
        "id": "1",
        "name": "Screen",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "children": [
            {
                "id": "2",
                "name": "Confirmation",
                "type": "FRAME",
                "layoutMode": "VERTICAL",
                "overlayPositionType": "CENTER",
                "overlayBackground": {"r": 0, "g": 0, "b": 0, "a": 0.4},
                "children": [
                    {
                        "id": "3",
                        "name": "Title",
                        "type": "TEXT",
                        "characters": "Done",
                    }
                ],
            }
        ],
    }
    tree, _, _, _ = build_clean_tree(root)

    assert tree.children[0].type == NodeType.DIALOG


def test_build_clean_tree_assigns_component_cluster_for_repeated_instances() -> None:
    from figma_flutter_agent.parser.dedup.clusters import component_cluster_id
    from figma_flutter_agent.parser.tree import build_clean_tree

    root = {
        "id": "1",
        "name": "Screen",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "children": [
            {
                "id": "2",
                "name": "State=Default",
                "type": "INSTANCE",
                "componentId": "comp-1",
            },
            {
                "id": "3",
                "name": "State=Hover",
                "type": "INSTANCE",
                "componentId": "comp-1",
            },
        ],
    }
    components = {"comp-1": {"name": "Button/Primary", "componentSetId": "set-1"}}
    component_sets = {"set-1": {"name": "Button"}}

    tree, _, dedup, cluster_summary = build_clean_tree(
        root,
        components=components,
        component_sets=component_sets,
    )

    cluster_id = component_cluster_id("comp-1")
    assert cluster_summary[cluster_id] == 2
    assert tree.children[0].cluster_id == cluster_id
    assert dedup.instance_count["comp-1"] == 2


def test_infer_leaf_type_handles_ellipse_and_shapes() -> None:
    assert infer_leaf_type({"type": "ELLIPSE", "name": "Circle"}) == NodeType.VECTOR
    assert infer_leaf_type({"type": "STAR", "name": "Star"}) == NodeType.VECTOR
    assert infer_leaf_type({"type": "LINE", "name": "Line"}) == NodeType.VECTOR
    assert infer_leaf_type({"type": "POLYGON", "name": "Triangle"}) == NodeType.VECTOR


def test_infer_leaf_type_handles_ellipse_with_image() -> None:
    node = {
        "type": "ELLIPSE",
        "name": "Avatar",
        "fills": [{"type": "IMAGE"}],
    }
    assert infer_leaf_type(node) == NodeType.IMAGE


def test_build_clean_tree_maps_instance_via_component_set_name() -> None:
    from figma_flutter_agent.parser.tree import build_clean_tree

    root = {
        "id": "1",
        "name": "Screen",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "children": [
            {
                "id": "2",
                "name": "State=Default",
                "type": "INSTANCE",
                "componentId": "comp-1",
            }
        ],
    }
    components = {"comp-1": {"name": "Default", "componentSetId": "set-1"}}
    component_sets = {"set-1": {"name": "Checkbox Field"}}

    tree, _, _, _ = build_clean_tree(root, components=components, component_sets=component_sets)

    assert tree.children[0].type == NodeType.CHECKBOX


def test_build_clean_tree_treats_section_like_frame() -> None:
    from figma_flutter_agent.parser.tree import build_clean_tree

    root = {
        "id": "1",
        "name": "Screen",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "children": [
            {
                "id": "2",
                "name": "Content Section",
                "type": "SECTION",
                "layoutMode": "VERTICAL",
                "children": [
                    {
                        "id": "3",
                        "name": "Title",
                        "type": "TEXT",
                        "characters": "Hello",
                    }
                ],
            }
        ],
    }
    tree, _, _, _ = build_clean_tree(root)

    section = tree.children[0]
    assert section.type == NodeType.COLUMN
    assert section.children[0].type == NodeType.TEXT


def test_build_clean_tree_treats_group_as_stack() -> None:
    from figma_flutter_agent.parser.tree import build_clean_tree

    root = {
        "id": "1",
        "name": "Screen",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "children": [
            {
                "id": "2",
                "name": "Overlay Group",
                "type": "GROUP",
                "children": [
                    {
                        "id": "3",
                        "name": "Badge",
                        "type": "TEXT",
                        "characters": "New",
                    }
                ],
            }
        ],
    }
    tree, _, _, _ = build_clean_tree(root)

    group = tree.children[0]
    assert group.type == NodeType.STACK
    assert group.children[0].type == NodeType.TEXT


def test_build_clean_tree_treats_layout_button_frame_as_button() -> None:
    from figma_flutter_agent.parser.tree import build_clean_tree

    root = {
        "id": "1",
        "name": "Screen",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "children": [
            {
                "id": "2",
                "name": "Primary Button",
                "type": "FRAME",
                "layoutMode": "HORIZONTAL",
                "children": [
                    {
                        "id": "3",
                        "name": "Continue",
                        "type": "TEXT",
                        "characters": "Continue",
                    }
                ],
            }
        ],
    }
    tree, _, _, _ = build_clean_tree(root)

    assert tree.children[0].type == NodeType.BUTTON


def test_extract_style_skips_hidden_text_fill() -> None:
    style = extract_style(
        {
            "type": "TEXT",
            "fills": [
                {"type": "SOLID", "visible": False, "color": {"r": 1, "g": 0, "b": 0, "a": 1}},
                {"type": "SOLID", "visible": True, "color": {"r": 0, "g": 0, "b": 0, "a": 1}},
            ],
            "style": {"fontSize": 16, "fontWeight": 400},
        },
        published_styles=None,
    )

    assert style.text_color == "0xFF000000"
