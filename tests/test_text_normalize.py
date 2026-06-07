"""Figma TEXT character normalization and truncation recovery."""

from figma_flutter_agent.parser.text_normalize import (
    has_figma_truncation_marker,
    recover_truncated_row_heading_text,
    strip_figma_truncation_marker,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
)


def _text_node(node_id: str, text: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=text,
        type=NodeType.TEXT,
        text=text,
        sizing=Sizing(width_mode=SizingMode.HUG, width=float(len(text) * 8)),
    )


def _chip_row(node_id: str, text: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="chip",
        type=NodeType.ROW,
        padding=Padding(left=12.0, right=12.0),
        sizing=Sizing(width_mode=SizingMode.FIXED, width=88.0, height=25.0),
        children=[_text_node(f"{node_id}:text", text)],
    )


def test_strip_figma_truncation_marker() -> None:
    assert strip_figma_truncation_marker("Заказ №2485…") == "Заказ №2485"
    assert has_figma_truncation_marker("Поддерж…")


def test_recover_truncated_row_heading_text_from_chip_prefix() -> None:
    row = CleanDesignTreeNode(
        id="row",
        name="row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=200.0),
        children=[
            CleanDesignTreeNode(
                id="title-col",
                name="title",
                type=NodeType.COLUMN,
                children=[_text_node("title-text", "Поддерж…")],
            ),
            _chip_row("chip", "Поддержка"),
        ],
    )

    recovered = recover_truncated_row_heading_text("Поддерж…", row=row)
    assert recovered == "Поддержка"
