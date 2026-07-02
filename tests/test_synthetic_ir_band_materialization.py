"""Tests for SyntheticIrBandMaterializationLaw."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.sectionize import materialize_band_clean_node
from figma_flutter_agent.generator.ir.tree import index_clean_tree, merge_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    SizingMode,
    WidgetIrKind,
    WidgetIrNode,
)


def _metric_child(node_id: str, *, top: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=NodeType.TEXT,
        text=node_id,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=80.0,
            height=20.0,
        ),
    )


def test_materialize_band_clean_node_builds_bounded_wrapper() -> None:
    """Law: SyntheticIrBandMaterializationLaw — IR band ids synthesize clean wrappers."""
    left = _metric_child("left", top=100.0)
    right = _metric_child("right", top=105.0)
    root = CleanDesignTreeNode(
        id="root",
        name="root",
        type=NodeType.STACK,
        children=[left, right],
    )
    ir_band = WidgetIrNode(
        figma_id="band-left",
        kind=WidgetIrKind.STACK,
        children=[
            WidgetIrNode(figma_id="left", kind=WidgetIrKind.TEXT),
            WidgetIrNode(figma_id="right", kind=WidgetIrKind.TEXT),
        ],
    )
    band = materialize_band_clean_node(ir_band, index_clean_tree(root))
    assert band is not None
    assert band.id == "band-left"
    assert {child.id for child in band.children} == {"left", "right"}


def test_merge_screen_ir_materializes_missing_band_children() -> None:
    """Law: merge keeps sectionize band children when clean root is still a STACK."""
    left = _metric_child("left", top=100.0)
    right = _metric_child("right", top=200.0)
    root = CleanDesignTreeNode(
        id="root",
        name="root",
        type=NodeType.STACK,
        children=[left, right],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.COLUMN,
            children=[
                WidgetIrNode(
                    figma_id="band-left",
                    kind=WidgetIrKind.STACK,
                    children=[WidgetIrNode(figma_id="left", kind=WidgetIrKind.TEXT)],
                ),
                WidgetIrNode(
                    figma_id="band-right",
                    kind=WidgetIrKind.STACK,
                    children=[WidgetIrNode(figma_id="right", kind=WidgetIrKind.TEXT)],
                ),
            ],
        ),
    )
    merged = merge_screen_ir(root, screen_ir)
    assert [child.id for child in merged.children] == ["band-left", "band-right"]
    assert merged.children[0].children[0].id == "left"
