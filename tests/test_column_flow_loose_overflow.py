"""Column flow slots in scroll hosts must not over-clamp with tight height pins."""

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


def _section_header_column() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="col:header",
        name="HeaderCol",
        type=NodeType.COLUMN,
        spacing=8.0,
        sizing=Sizing(width=200.0, height=72.0, height_mode=SizingMode.FIXED),
        children=[
            CleanDesignTreeNode(
                id="col:title",
                name="Title",
                type=NodeType.TEXT,
                text="SECTION HEADER",
                sizing=Sizing(width=180.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="col:sub",
                name="Subtitle",
                type=NodeType.TEXT,
                text="View all items",
                sizing=Sizing(width=180.0, height=20.0),
            ),
        ],
    )


def test_spaced_column_in_bounded_row_uses_loose_overflow_shell() -> None:
    """Law: column_flow_slot_must_not_over_clamp."""
    column = _section_header_column()
    row = CleanDesignTreeNode(
        id="row:slot",
        name="SlotRow",
        type=NodeType.ROW,
        sizing=Sizing(width=300.0, height=72.0, height_mode=SizingMode.FILL),
        children=[column],
    )
    body = render_node_body(
        column,
        uses_svg=False,
        parent_type=NodeType.ROW,
        parent_node=row,
    )
    compact = body.replace("\n", "")
    assert (
        "OverflowBox(" in compact
        or "ConstrainedBox(constraints: BoxConstraints(minHeight:" in compact
    )
    assert "SizedBox(height: 72.0, child: Column(" not in compact
