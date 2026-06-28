from figma_flutter_agent.assets.composite_icons import (
    collect_figma_composite_icon_groups,
    is_figma_composite_icon_node,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement


def test_is_figma_composite_icon_node_detects_small_vector_group() -> None:
    node = {
        "id": "1:1",
        "type": "FRAME",
        "visible": True,
        "name": "Google",
        "absoluteBoundingBox": {"width": 24.0, "height": 24.0},
        "children": [
            {"id": "1:2", "type": "VECTOR", "visible": True},
            {"id": "1:3", "type": "VECTOR", "visible": True},
        ],
    }
    assert is_figma_composite_icon_node(node)


def test_collect_figma_composite_icon_groups_skips_child_vectors() -> None:
    root = {
        "id": "0:1",
        "type": "FRAME",
        "visible": True,
        "children": [
            {
                "id": "1:1",
                "type": "FRAME",
                "visible": True,
                "name": "icon",
                "absoluteBoundingBox": {"width": 20.0, "height": 20.0},
                "children": [
                    {"id": "1:2", "type": "VECTOR", "visible": True},
                    {"id": "1:3", "type": "VECTOR", "visible": True},
                ],
            },
            {"id": "9:9", "type": "VECTOR", "visible": True, "name": "solo"},
        ],
    }
    parents, skip = collect_figma_composite_icon_groups(root)
    assert parents == frozenset({"1:1"})
    assert skip == frozenset({"1:2", "1:3"})
    assert "9:9" not in skip


def test_is_figma_composite_icon_node_detects_nested_stack_layers() -> None:
    """Law: compact_icon_renders_as_single_asset — nested stacks count as multicolor icon."""
    node = {
        "id": "1:1",
        "type": "INSTANCE",
        "visible": True,
        "name": "Countries/United Kingdom",
        "absoluteBoundingBox": {"width": 18.0, "height": 18.0},
        "children": [
            {
                "id": "1:2",
                "type": "FRAME",
                "visible": True,
                "name": "Circle/George Cross",
                "absoluteBoundingBox": {"width": 18.0, "height": 18.0},
                "children": [
                    {"id": "1:3", "type": "VECTOR", "visible": True},
                ],
            },
            {
                "id": "1:4",
                "type": "FRAME",
                "visible": True,
                "name": "Canton",
                "absoluteBoundingBox": {"width": 9.0, "height": 9.0},
                "children": [
                    {"id": "1:5", "type": "VECTOR", "visible": True},
                ],
            },
        ],
    }
    assert is_figma_composite_icon_node(node)


def test_compact_multilayer_flag_emits_single_svg_not_overflow_stack() -> None:
    """Law: compact_icon_renders_as_single_asset."""
    from figma_flutter_agent.assets.composite_icons import is_composite_icon_export_node
    from figma_flutter_agent.generator.layout.widgets import render_node_body
    from figma_flutter_agent.generator.subtree import collect_subtree_widget_specs

    flag = CleanDesignTreeNode(
        id="I49:1748;3:6100",
        name="Countries/United Kingdom",
        type=NodeType.STACK,
        sizing=Sizing(width=18.0, height=18.0),
        vector_asset_key="assets/icons/countries_united_kingdom_I49_1748;3_6100.svg",
        children=[
            CleanDesignTreeNode(
                id="layer-a",
                name="Circle/George Cross",
                type=NodeType.STACK,
                sizing=Sizing(width=18.0, height=18.0),
                children=[
                    CleanDesignTreeNode(
                        id="vec-a",
                        name="Background",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=18.0, height=18.0),
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="layer-b",
                name="Canton",
                type=NodeType.STACK,
                sizing=Sizing(width=9.0, height=9.0),
                children=[
                    CleanDesignTreeNode(
                        id="vec-b",
                        name="Canton",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=9.0, height=9.0),
                    ),
                ],
            ),
        ],
    )
    assert is_composite_icon_export_node(flag)
    specs = collect_subtree_widget_specs(flag, widget_suffix="Widget")
    assert specs == []
    body = render_node_body(flag, uses_svg=True)
    compact = body.replace("\n", "")
    assert "OverflowBox(" not in compact
    assert "countries_united_kingdom_I49_1748;3_6100.svg" in compact
    assert compact.count("SvgPicture.asset") == 1


def test_collect_button_icon_group_exports_parent_not_vectors() -> None:
    root = {
        "id": "0:1",
        "type": "FRAME",
        "visible": True,
        "name": "Continue with Google Button",
        "children": [
            {
                "id": "1:1",
                "type": "FRAME",
                "visible": True,
                "name": "Google icon",
                "absoluteBoundingBox": {"width": 24.0, "height": 24.0},
                "children": [
                    {"id": "1:2", "type": "VECTOR", "visible": True},
                    {"id": "1:3", "type": "VECTOR", "visible": True},
                ],
            },
            {
                "id": "1:4",
                "type": "TEXT",
                "visible": True,
                "name": "Label",
                "characters": "CONTINUE WITH GOOGLE",
            },
        ],
    }
    parents, skip = collect_figma_composite_icon_groups(root)
    assert parents == frozenset({"1:1"})
    assert skip == frozenset({"1:2", "1:3"})
    assert "1:4" not in skip


def test_collect_exportable_nodes_exports_button_icon_group_parent() -> None:
    from figma_flutter_agent.assets.collect import collect_exportable_nodes

    root = {
        "id": "0:1",
        "type": "FRAME",
        "visible": True,
        "name": "Screen",
        "children": [
            {
                "id": "1:0",
                "type": "FRAME",
                "visible": True,
                "name": "Button",
                "children": [
                    {
                        "id": "1:1",
                        "type": "FRAME",
                        "visible": True,
                        "name": "SVG",
                        "absoluteBoundingBox": {"width": 24.0, "height": 24.0},
                        "children": [
                            {"id": "1:2", "type": "VECTOR", "visible": True},
                        ],
                    },
                ],
            },
        ],
    }
    items = collect_exportable_nodes(root, exclude_node_ids={"0:1"})
    icon_ids = {node_id for node_id, _, kind in items if kind == "icon"}
    assert icon_ids == {"1:1"}


def test_protected_background_vector_not_decorative() -> None:
    from figma_flutter_agent.parser.dedup.prune import is_decorative_absolute_vector

    root = CleanDesignTreeNode(
        id="0",
        name="screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="bg",
                name="SignInBackground",
                type=NodeType.STACK,
                sizing=Sizing(width=414.0, height=896.0),
                stack_placement=StackPlacement(left=0.0, top=0.0, width=414.0, height=896.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="v",
                name="Vector",
                type=NodeType.VECTOR,
                layout_positioning="ABSOLUTE",
                sizing=Sizing(width=200.0, height=200.0),
                stack_placement=StackPlacement(left=20.0, top=30.0, width=200.0, height=200.0),
            ),
        ],
    )
    vector = root.children[1]
    assert not is_decorative_absolute_vector(vector, root=root)
