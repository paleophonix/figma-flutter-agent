"""Archetype emit fast-path gating (Track T / T3c)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing, StackPlacement


def _consent_row_node() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:row",
        name="Consent",
        type=NodeType.ROW,
        sizing=Sizing(width=374.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Policy",
                type=NodeType.TEXT,
                text="I agree",
                sizing=Sizing(width=300.0, height=20.0),
            ),
            CleanDesignTreeNode(
                id="1:box",
                name="Checkbox",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=24.0, height=24.0),
                style=NodeStyle(border_color="0xFF000000", border_width=1.0),
            ),
        ],
    )


def test_de_archetype_pass_skips_consent_fast_path() -> None:
    node = _consent_row_node()
    with_fast = render_node_body(node, uses_svg=False, de_archetype_pass=False)
    without_fast = render_node_body(node, uses_svg=False, de_archetype_pass=True)
    assert with_fast != without_fast or "Row(" in without_fast
