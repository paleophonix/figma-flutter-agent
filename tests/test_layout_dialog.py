"""Tests for dialog semantic layout and prototype overlay routing."""

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.navigation_codegen import build_prototype_actions
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.parser.prototype import (
    build_prototype_navigation_plan,
    collect_prototype_links,
    index_frames,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_dialog_semantic_renders_alert_dialog() -> None:
    dialog = CleanDesignTreeNode(
        id="1",
        name="Delete confirmation",
        type=NodeType.DIALOG,
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Message",
                type=NodeType.TEXT,
                text="This cannot be undone.",
            ),
        ],
    )

    layout = render_layout_file(dialog, feature_name="confirm", uses_svg=False)[
        "lib/generated/confirm_layout.dart"
    ]

    assert "AlertDialog(" in layout
    assert "title: Text('Delete confirmation')" in layout
    assert "Navigator.of(context).pop()" in layout
    assert "This cannot be undone." in layout


def test_overlay_to_dialog_destination_uses_show_dialog() -> None:
    root = {
        "id": "1:1",
        "name": "Home",
        "type": "FRAME",
        "children": [
            {
                "id": "1:2",
                "name": "Open",
                "type": "FRAME",
                "reactions": [
                    {
                        "trigger": {"type": "ON_CLICK"},
                        "action": {
                            "type": "NODE",
                            "navigation": "OVERLAY",
                            "destinationId": "2:1",
                        },
                    }
                ],
            }
        ],
    }
    destination = {"id": "2:1", "name": "Confirm Dialog", "type": "FRAME"}
    links = collect_prototype_links(root)
    plan = build_prototype_navigation_plan(
        "home",
        frame_index=index_frames(root, destination),
        links=links,
        root_node_id="1:1",
    )

    actions = build_prototype_actions(plan)

    assert actions[0].overlay_style == "dialog"
    renderer = DartRenderer()
    files = renderer.render_prototype_navigation(actions, routing_type="none")
    source = files["lib/core/prototype_navigation.dart"]

    assert "showDialog<void>" in source
    assert "showModalBottomSheet" not in source
