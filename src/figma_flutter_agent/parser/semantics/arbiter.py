"""Staged arbitration and rollback for semantic classification."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.models import Classification, DetectorContext, SignalTier
from figma_flutter_agent.parser.semantics.prefilter import _OVERLAY_KINDS
from figma_flutter_agent.parser.semantics.report import ArbitrationOutcome
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrKind
from figma_flutter_agent.schemas.ir_payloads import payload_for_kind


def _tier_weight(tier: SignalTier) -> float:
    if tier == SignalTier.PROPERTIES:
        return 1.0
    if tier == SignalTier.ANATOMY:
        return 0.9
    return 0.7


def _cap_geometry(confidence: float, tier: SignalTier) -> float:
    if tier == SignalTier.GEOMETRY:
        return min(confidence, 0.7)
    return confidence


def merge_signals(ctx: DetectorContext) -> DetectorContext:
    """Merge tier signal collectors onto the detector context."""
    from figma_flutter_agent.parser.semantics.models import TierSignals
    from figma_flutter_agent.parser.semantics.signals import (
        collect_anatomy_signals,
        collect_geometry_signals,
        collect_property_signals,
    )

    properties = collect_property_signals(ctx.clean_node)
    anatomy = collect_anatomy_signals(ctx.clean_node)
    geometry = collect_geometry_signals(ctx.clean_node)
    merged = TierSignals(
        properties_score=properties.properties_score,
        anatomy_score=anatomy.anatomy_score,
        geometry_score=geometry.geometry_score,
        property_hits=properties.property_hits,
        anatomy_hits=anatomy.anatomy_hits,
        geometry_hits=geometry.geometry_hits,
        overlay_signal=properties.overlay_signal,
        hard_reject_kinds=properties.hard_reject_kinds,
    )
    return DetectorContext(
        clean_node=ctx.clean_node,
        ir_node=ctx.ir_node,
        clean_by_id=ctx.clean_by_id,
        screen_ir=ctx.screen_ir,
        signals=merged,
        confidence_threshold=ctx.confidence_threshold,
        grey_zone_min=ctx.grey_zone_min,
        llm_hint=ctx.llm_hint,
    )


def _composite_dropdown_vetoed(ctx: DetectorContext, kind: WidgetIrKind) -> bool:
    """Reject single-select dropdown kinds on multi-control composite hosts."""
    if kind != WidgetIrKind.INPUT_DROPDOWN:
        return False
    node = ctx.clean_node
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    descendants = _descendant_nodes(node, 5)
    input_count = sum(1 for item in descendants if item.type == NodeType.INPUT)
    if input_count >= 2:
        return True
    if any(item.type == NodeType.SLIDER for item in descendants):
        return True
    return len(node.children) >= 3 and node.type in {NodeType.STACK, NodeType.COLUMN, NodeType.ROW}


def arbitrate(
    candidates: list[Classification],
    ctx: DetectorContext,
) -> ArbitrationOutcome:
    """Pick the winning kind or roll back to layout emit."""
    if not candidates:
        return _maybe_llm_hint(ctx, runner_up_kind=None, runner_up_confidence=0.0)

    ranked = sorted(
        candidates,
        key=lambda item: (_tier_weight(item.winning_tier) * item.confidence, item.confidence),
        reverse=True,
    )
    winner = ranked[0]
    confidence = _cap_geometry(winner.confidence, winner.winning_tier)

    if winner.kind in _OVERLAY_KINDS and not ctx.signals.overlay_signal:
        vetoed = [item for item in ranked if item.kind not in _OVERLAY_KINDS]
        if not vetoed:
            return ArbitrationOutcome(
                kind=None,
                confidence=confidence,
                evidence={**winner.evidence, "overlayVeto": True},
                payload=None,
                bucket="rejectedByInvariant",
                reject_reason="overlay_without_t1_signal",
                runner_up_kind=winner.kind.value,
            )
        winner = vetoed[0]
        confidence = _cap_geometry(winner.confidence, winner.winning_tier)

    if _composite_dropdown_vetoed(ctx, winner.kind):
        vetoed = [item for item in ranked if item.kind != WidgetIrKind.INPUT_DROPDOWN]
        if not vetoed:
            return ArbitrationOutcome(
                kind=None,
                confidence=confidence,
                evidence={**winner.evidence, "compositeDropdownVeto": True},
                payload=None,
                bucket="rejectedByInvariant",
                reject_reason="composite_dropdown_veto",
                runner_up_kind=winner.kind.value,
            )
        winner = vetoed[0]
        confidence = _cap_geometry(winner.confidence, winner.winning_tier)

    if confidence >= ctx.confidence_threshold:
        payload = payload_for_kind(winner.kind, ir_node=ctx.ir_node)
        bucket = "llmAnnotationUsed" if winner.evidence.get("source") == "llm_hint" else "accepted"
        return ArbitrationOutcome(
            kind=winner.kind,
            confidence=confidence,
            evidence=winner.evidence,
            payload=payload,
            bucket=bucket,
        )

    if ctx.grey_zone_min <= confidence < ctx.confidence_threshold:
        hint_outcome = _consult_llm_hint(ctx, winner)
        if hint_outcome.kind is not None and hint_outcome.payload is None:
            hint_outcome = ArbitrationOutcome(
                kind=hint_outcome.kind,
                confidence=hint_outcome.confidence,
                evidence=hint_outcome.evidence,
                payload=payload_for_kind(hint_outcome.kind, ir_node=ctx.ir_node),
                bucket=hint_outcome.bucket,
            )
        if hint_outcome.kind is not None:
            return hint_outcome

    return ArbitrationOutcome(
        kind=None,
        confidence=confidence,
        evidence=winner.evidence,
        payload=None,
        bucket="rejectedBelowThreshold",
        reject_reason="below_confidence_threshold",
        runner_up_kind=winner.kind.value,
    )


def _consult_llm_hint(
    ctx: DetectorContext,
    structural: Classification,
) -> ArbitrationOutcome:
    hint = ctx.llm_hint
    if hint is None:
        return ArbitrationOutcome(
            kind=None,
            confidence=0.0,
            evidence={},
            payload=None,
            bucket=None,
        )
    suggested = WidgetIrKind(hint.suggested_kind)
    if _nav_bottom_bar_hint_vetoed(ctx, suggested):
        return ArbitrationOutcome(
            kind=None,
            confidence=0.0,
            evidence={"llmRejected": "nav_bottom_bar_screen_frame"},
            payload=None,
            bucket=None,
        )
    if suggested in ctx.signals.hard_reject_kinds:
        return ArbitrationOutcome(
            kind=None,
            confidence=0.0,
            evidence={"llmRejected": "hard_reject"},
            payload=None,
            bucket=None,
        )
    if suggested in _OVERLAY_KINDS and not ctx.signals.overlay_signal:
        return ArbitrationOutcome(
            kind=None,
            confidence=0.0,
            evidence={"llmRejected": "overlay_without_t1"},
            payload=None,
            bucket=None,
        )
    if hint.confidence < ctx.grey_zone_min:
        return ArbitrationOutcome(
            kind=None,
            confidence=0.0,
            evidence={},
            payload=None,
            bucket=None,
        )
    if (
        structural.confidence > 0
        and structural.kind != suggested
        and structural.winning_tier in {SignalTier.PROPERTIES, SignalTier.ANATOMY}
        and structural.confidence >= ctx.grey_zone_min
    ):
        return ArbitrationOutcome(
            kind=None,
            confidence=0.0,
            evidence={"llmRejected": "structural_veto"},
            payload=None,
            bucket=None,
        )
    return ArbitrationOutcome(
        kind=suggested,
        confidence=hint.confidence,
        evidence={"source": "llm_hint", "structural_runner_up": structural.kind.value},
        payload=None,
        bucket="llmAnnotationUsed",
    )


def _nav_bottom_bar_hint_vetoed(ctx: DetectorContext, suggested: WidgetIrKind) -> bool:
    """Return True when a nav hint must not apply to the current clean node."""
    from figma_flutter_agent.generator.ir.validate.root_kind import (
        nav_bottom_bar_kind_contradicts_clean_node,
    )

    return (
        suggested == WidgetIrKind.NAV_BOTTOM_BAR
        and nav_bottom_bar_kind_contradicts_clean_node(ctx.clean_node)
    )


def _maybe_llm_hint(
    ctx: DetectorContext,
    *,
    runner_up_kind: str | None,
    runner_up_confidence: float,
) -> ArbitrationOutcome:
    hint = ctx.llm_hint
    if hint is None or hint.confidence < ctx.confidence_threshold:
        return ArbitrationOutcome(
            kind=None,
            confidence=runner_up_confidence,
            evidence={},
            payload=None,
            bucket="rejectedBelowThreshold" if runner_up_kind else None,
            reject_reason="no_candidates" if not runner_up_kind else "below_confidence_threshold",
            runner_up_kind=runner_up_kind,
        )
    suggested = WidgetIrKind(hint.suggested_kind)
    if _nav_bottom_bar_hint_vetoed(ctx, suggested):
        return ArbitrationOutcome(
            kind=None,
            confidence=0.0,
            evidence={"llmRejected": "nav_bottom_bar_screen_frame"},
            payload=None,
            bucket="rejectedBelowThreshold",
            reject_reason="llm_hint_rejected",
            runner_up_kind=runner_up_kind,
        )
    if suggested in ctx.signals.hard_reject_kinds:
        return ArbitrationOutcome(
            kind=None,
            confidence=0.0,
            evidence={"llmRejected": "hard_reject"},
            payload=None,
            bucket="rejectedBelowThreshold",
            reject_reason="llm_hint_rejected",
            runner_up_kind=runner_up_kind,
        )
    if suggested in _OVERLAY_KINDS and not ctx.signals.overlay_signal:
        return ArbitrationOutcome(
            kind=None,
            confidence=0.0,
            evidence={"llmRejected": "overlay_without_t1"},
            payload=None,
            bucket="rejectedByInvariant",
            reject_reason="overlay_without_t1_signal",
            runner_up_kind=suggested.value,
        )
    payload = payload_for_kind(suggested, ir_node=ctx.ir_node)
    return ArbitrationOutcome(
        kind=suggested,
        confidence=hint.confidence,
        evidence={"source": "llm_hint_only"},
        payload=payload,
        bucket="llmAnnotationUsed",
    )
