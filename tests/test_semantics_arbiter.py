"""Arbiter threshold and LLM hint arbitration tests."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.arbiter import arbitrate
from figma_flutter_agent.parser.semantics.models import (
    Classification,
    DetectorContext,
    SignalTier,
    TierSignals,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)
from figma_flutter_agent.schemas.ir_payloads import LlmClassificationHint


def _ctx(*, overlay: bool = False, threshold: float = 0.8, grey: float = 0.5) -> DetectorContext:
    clean = CleanDesignTreeNode(id="n1", name="n", type=NodeType.BUTTON)
    ir = WidgetIrNode(figma_id="n1")
    return DetectorContext(
        clean_node=clean,
        ir_node=ir,
        clean_by_id={"n1": clean},
        screen_ir=ScreenIr(root=ir),
        signals=TierSignals(overlay_signal=overlay),
        confidence_threshold=threshold,
        grey_zone_min=grey,
    )


def test_arbiter_accepts_above_threshold() -> None:
    ctx = _ctx()
    candidates = [
        Classification(
            kind=WidgetIrKind.BUTTON_FILLED,
            confidence=0.9,
            winning_tier=SignalTier.ANATOMY,
        )
    ]
    outcome = arbitrate(candidates, ctx)
    assert outcome.kind == WidgetIrKind.BUTTON_FILLED
    assert outcome.confidence >= 0.8
    assert outcome.payload is not None
    assert outcome.bucket == "accepted"


def test_arbiter_rolls_back_overlay_without_t1() -> None:
    ctx = _ctx(overlay=False)
    candidates = [
        Classification(
            kind=WidgetIrKind.OVERLAY_DIALOG,
            confidence=0.95,
            winning_tier=SignalTier.GEOMETRY,
        )
    ]
    outcome = arbitrate(candidates, ctx)
    assert outcome.kind is None
    assert outcome.payload is None
    assert outcome.bucket == "rejectedByInvariant"


def test_arbiter_rejects_llm_hint_in_hard_reject() -> None:
    ctx = _ctx(grey=0.5)
    ctx = DetectorContext(
        clean_node=ctx.clean_node,
        ir_node=ctx.ir_node,
        clean_by_id=ctx.clean_by_id,
        screen_ir=ctx.screen_ir,
        signals=TierSignals(hard_reject_kinds=frozenset({WidgetIrKind.BUTTON_FILLED})),
        confidence_threshold=0.8,
        grey_zone_min=0.5,
        llm_hint=LlmClassificationHint(suggested_kind="button_filled", confidence=0.9),
    )
    outcome = arbitrate([], ctx)
    assert outcome.kind is None
