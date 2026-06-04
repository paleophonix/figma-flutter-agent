"""Tests for design coverage report."""

from __future__ import annotations

from figma_flutter_agent.parser.design_coverage import build_design_coverage_report
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


def test_coverage_counts_interactive_and_keys() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Go",
                type=NodeType.BUTTON,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=100, height=40),
            ),
        ],
    )
    planned = {
        "lib/generated/demo_layout.dart": (
            "Positioned(key: ValueKey('figma-1_2'), child: ElevatedButton(onPressed: () {}))"
        ),
    }
    report = build_design_coverage_report(root, planned)
    assert report["interactiveNodeCount"] == 1
    assert report["interactiveWithValueKey"] == 1
    assert report["uncoveredInteractive"] == []
