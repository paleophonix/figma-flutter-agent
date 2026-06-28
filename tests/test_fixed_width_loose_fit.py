"""Fixed-width flex children under tight columns must keep loose intrinsic width."""

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
)


def test_fixed_width_button_under_narrow_column_uses_loose_flex() -> None:
    """Law: fixed_width_child_loose_fit_under_tight_parent."""
    button = CleanDesignTreeNode(
        id="btn:1",
        name="Continue",
        type=NodeType.BUTTON,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=280.0,
            height=48.0,
        ),
        style=NodeStyle(background_color="0xFF111111", border_radius=12.0),
        children=[
            CleanDesignTreeNode(
                id="btn:label",
                name="Label",
                type=NodeType.TEXT,
                text="Continue",
                sizing=Sizing(width=120.0, height=20.0),
            )
        ],
    )
    column = CleanDesignTreeNode(
        id="col:form",
        name="Form",
        type=NodeType.COLUMN,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            width=240.0,
            height=400.0,
        ),
        children=[button],
    )
    body = render_node_body(
        button,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
        parent_node=column,
    )
    compact = body.replace("\n", "")
    assert "Expanded(" not in compact
    assert (
        "Flexible(fit: FlexFit.loose" in compact
        or "Align(alignment:" in compact
        or "SizedBox(width: 280.0" in compact
    )


def test_fixed_width_row_wider_than_column_parent_uses_loose_flex() -> None:
    row = CleanDesignTreeNode(
        id="row:actions",
        name="Actions",
        type=NodeType.ROW,
        spacing=12.0,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=280.0,
            height=48.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="row:primary",
                name="Primary",
                type=NodeType.BUTTON,
                sizing=Sizing(width=134.0, height=48.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="row:secondary",
                name="Secondary",
                type=NodeType.BUTTON,
                sizing=Sizing(width=134.0, height=48.0),
                children=[],
            ),
        ],
    )
    column = CleanDesignTreeNode(
        id="col:shell",
        name="Shell",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=240.0, height=500.0),
        children=[row],
    )
    body = render_node_body(
        row,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
        parent_node=column,
    )
    compact = body.replace("\n", "")
    assert "Expanded(" not in compact
    assert "Flexible(fit: FlexFit.loose" in compact or "Align(alignment:" in compact
