"""Chip-input detector guardrails."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.detectors.actions import ACTION_DETECTORS
from figma_flutter_agent.parser.semantics.models import DetectorContext, TierSignals
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def _chip_input_detector():
    return next(item for item in ACTION_DETECTORS if item.kind == WidgetIrKind.CHIP_INPUT)


def test_static_segmented_number_row_not_chip_input() -> None:
    node = CleanDesignTreeNode(
        id="card-number",
        name="Group",
        type=NodeType.STACK,
        sizing=Sizing(width=196.0, height=26.0),
        children=[
            CleanDesignTreeNode(
                id="seg-1",
                name="4756",
                type=NodeType.TEXT,
                text="4756",
                stack_placement=StackPlacement(left=0.0, width=48.0, height=26.0),
            ),
            CleanDesignTreeNode(
                id="seg-2",
                name="7890",
                type=NodeType.TEXT,
                text="7890",
                stack_placement=StackPlacement(left=52.0, width=48.0, height=26.0),
            ),
        ],
    )
    ctx = DetectorContext(
        clean_node=node,
        ir_node=WidgetIrNode(figma_id="card-number"),
        clean_by_id={"card-number": node},
        screen_ir=ScreenIr(root=WidgetIrNode(figma_id="root")),
        signals=TierSignals(),
        confidence_threshold=0.8,
        grey_zone_min=0.5,
    )
    assert _chip_input_detector().detect(ctx) is None


def test_row_with_inputs_still_chip_input() -> None:
    node = CleanDesignTreeNode(
        id="chip-row",
        name="Row",
        type=NodeType.ROW,
        children=[
            CleanDesignTreeNode(id="a", name="A", type=NodeType.INPUT),
            CleanDesignTreeNode(id="b", name="B", type=NodeType.INPUT),
        ],
    )
    ctx = DetectorContext(
        clean_node=node,
        ir_node=WidgetIrNode(figma_id="chip-row"),
        clean_by_id={"chip-row": node},
        screen_ir=ScreenIr(root=WidgetIrNode(figma_id="root")),
        signals=TierSignals(),
        confidence_threshold=0.8,
        grey_zone_min=0.5,
    )
    assert _chip_input_detector().detect(ctx) is not None
