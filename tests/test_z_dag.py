"""Unified Z-DAG ordering (WP-6)."""

from __future__ import annotations

from figma_flutter_agent.parser.z_dag import ghost_occlusion_violations, z_dag_sort
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_z_dag_demotes_decor_below_interactive() -> None:
    decor = CleanDesignTreeNode(
        id="decor",
        name="Decor",
        type=NodeType.VECTOR,
        sizing=Sizing(width=100.0, height=100.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=100.0, height=100.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=80.0, height=40.0),
        stack_placement=StackPlacement(left=10.0, top=10.0, width=80.0, height=40.0),
    )
    ordered = z_dag_sort([button, decor])
    assert ordered[0].id == "decor"
    assert ordered[1].id == "btn"
    assert not ghost_occlusion_violations(ordered)


def test_z_dag_no_cycle_on_presentational_interactive_overlap() -> None:
    """Interactive render_boundary must not create decor/interactive cycle."""
    button = CleanDesignTreeNode(
        id="btn",
        name="Button",
        type=NodeType.BUTTON,
        render_boundary=True,
        sizing=Sizing(width=80.0, height=40.0),
        stack_placement=StackPlacement(left=10.0, top=10.0, width=80.0, height=40.0),
    )
    decor = CleanDesignTreeNode(
        id="decor",
        name="Decor",
        type=NodeType.VECTOR,
        sizing=Sizing(width=100.0, height=100.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=100.0, height=100.0),
    )
    ordered = z_dag_sort([decor, button])
    assert len(ordered) == 2
    assert not ghost_occlusion_violations(ordered)
