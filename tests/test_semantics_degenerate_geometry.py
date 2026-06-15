"""Semantic detector resilience for zero and missing extents."""

from __future__ import annotations

import pytest

from figma_flutter_agent.parser.semantics.detectors.display import DISPLAY_DETECTORS
from figma_flutter_agent.parser.semantics.models import DetectorContext, TierSignals
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    ScreenIr,
    Sizing,
    WidgetIrKind,
    WidgetIrNode,
)


def _media_avatar_detector():
    return next(item for item in DISPLAY_DETECTORS if item.kind == WidgetIrKind.MEDIA_AVATAR)


def _detector_ctx(node: CleanDesignTreeNode) -> DetectorContext:
    ir = WidgetIrNode(figma_id=node.id)
    return DetectorContext(
        clean_node=node,
        ir_node=ir,
        clean_by_id={node.id: node},
        screen_ir=ScreenIr(root=ir),
        signals=TierSignals(),
        confidence_threshold=0.8,
        grey_zone_min=0.5,
    )


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (8.0, 0.0),
        (0.0, 8.0),
        (0.0, 0.0),
    ],
)
def test_media_avatar_detector_rejects_non_positive_extent(width: float, height: float) -> None:
    node = CleanDesignTreeNode(
        id="degenerate-vector",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=width, height=height),
        style=NodeStyle(has_stroke=True),
    )
    detector = _media_avatar_detector()
    assert detector.detect(_detector_ctx(node)) is None


def test_media_avatar_detector_accepts_square_avatar_extent() -> None:
    node = CleanDesignTreeNode(
        id="avatar",
        name="Avatar",
        type=NodeType.IMAGE,
        sizing=Sizing(width=48.0, height=48.0),
    )
    detector = _media_avatar_detector()
    result = detector.detect(_detector_ctx(node))
    assert result is not None
    assert result.kind == WidgetIrKind.MEDIA_AVATAR


def test_classify_screen_ir_survives_zero_height_vector_subtree() -> None:
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.parser.semantics.classify import classify_screen_ir

    vector = CleanDesignTreeNode(
        id="103:596",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=8.0, height=0.0),
        style=NodeStyle(has_stroke=True, border_width=2.0),
    )
    group = CleanDesignTreeNode(
        id="103:595",
        name="Group",
        type=NodeType.STACK,
        sizing=Sizing(width=8.0, height=8.0),
        children=[vector],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        children=[group],
    )
    updated, _report = classify_screen_ir(default_screen_ir(screen), screen)
    assert updated.root is not None
    kind = _find_kind(updated.root, "103:596")
    assert kind != WidgetIrKind.MEDIA_AVATAR.value


def _find_kind(node: WidgetIrNode, figma_id: str) -> str | None:
    if node.figma_id == figma_id:
        return node.kind.value if hasattr(node.kind, "value") else str(node.kind)
    for child in node.children:
        found = _find_kind(child, figma_id)
        if found is not None:
            return found
    return None
