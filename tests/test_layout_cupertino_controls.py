"""Cupertino form controls in deterministic layout."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_cupertino_button_and_input_in_layout() -> None:
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="1",
                name="Continue",
                type=NodeType.BUTTON,
                sizing=Sizing(width=200.0, height=48.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="2",
                name="Email",
                type=NodeType.INPUT,
                sizing=Sizing(width=374.0, height=63.0),
                children=[],
            ),
        ],
    )
    layout = render_layout_file(
        screen,
        feature_name="auth",
        uses_svg=False,
        theme_variant="cupertino",
    )["lib/generated/auth_layout.dart"]
    assert "CupertinoButton.filled(" in layout
    assert "CupertinoTextField(" in layout
    assert "decoration: InputDecoration" not in layout
