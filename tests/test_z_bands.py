"""Semantic Z-band ordering tests (RC-8)."""

from __future__ import annotations

from figma_flutter_agent.parser.z_bands import semantic_z_sort
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_presentational_renderboundary_below_interactive() -> None:
    decor = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.CONTAINER,
        render_boundary=True,
        style=__import__("figma_flutter_agent.schemas", fromlist=["NodeStyle"]).NodeStyle(),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=300.0, height=600.0),
    )
    field = CleanDesignTreeNode(
        id="input",
        name="Input",
        type=NodeType.INPUT,
        stack_placement=StackPlacement(left=20.0, top=400.0, width=260.0, height=48.0),
    )
    ordered = semantic_z_sort([field, decor])
    assert ordered[0].id == "bg"
    assert ordered[1].id == "input"
