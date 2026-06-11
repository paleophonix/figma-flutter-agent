"""Tests for parser interaction signal collection."""

from __future__ import annotations

from figma_flutter_agent.parser.interaction import collect_interaction_signals
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


def test_collect_interaction_signals_includes_pill_geometry() -> None:
    root = CleanDesignTreeNode(
        id="row",
        name="chip-row",
        type=NodeType.ROW,
        children=[
            CleanDesignTreeNode(
                id="chip-1",
                name="amount-chip",
                type=NodeType.BUTTON,
                sizing=Sizing(
                    width_mode=SizingMode.FIXED,
                    height_mode=SizingMode.FIXED,
                    width=60.0,
                    height=32.0,
                ),
            ),
        ],
    )
    signals = collect_interaction_signals(root)
    assert "chip-1" in signals
    assert signals["chip-1"].get("pillLike") is True
