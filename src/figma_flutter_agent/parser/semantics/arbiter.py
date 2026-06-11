"""Staged arbitration and rollback for semantic classification."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.models import Classification, DetectorContext, SignalTier
from figma_flutter_agent.parser.semantics.prefilter import _OVERLAY_KINDS
from figma_flutter_agent.schemas import WidgetIrKind
from figma_flutter_agent.schemas.ir_payloads import KindPayload, payload_for_kind


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


def arbitrate(
    candidates: list[Classification],
    ctx: DetectorContext,
) -> tuple[WidgetIrKind | None, float, dict[str, object], KindPayload | None]:
    """Pick the winning kind or roll back to layout emit."""
    if not candidates:
        return _maybe_llm_hint(ctx)

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
            return _maybe_llm_hint(ctx)
        winner = vetoed[0]
        confidence = _cap_geometry(winner.confidence, winner.winning_tier)

    if confidence >= ctx.confidence_threshold:
        payload = payload_for_kind(winner.kind, ir_node=ctx.ir_node)
        return winner.kind, confidence, winner.evidence, payload

    if ctx.grey_zone_min <= confidence < ctx.confidence_threshold:
        hint_kind, hint_confidence, hint_evidence = _consult_llm_hint(ctx, winner)
        if hint_kind is not None:
            payload = payload_for_kind(hint_kind, ir_node=ctx.ir_node)
            return hint_kind, hint_confidence, hint_evidence, payload

    return _maybe_llm_hint(ctx)


def _consult_llm_hint(
    ctx: DetectorContext,
    structural: Classification,
) -> tuple[WidgetIrKind | None, float, dict[str, object]]:
    hint = ctx.llm_hint
    if hint is None:
        return None, 0.0, {}
    suggested = WidgetIrKind(hint.suggested_kind)
    if suggested in ctx.signals.hard_reject_kinds:
        return None, 0.0, {}
    if suggested in _OVERLAY_KINDS and not ctx.signals.overlay_signal:
        return None, 0.0, {}
    if hint.confidence < ctx.grey_zone_min:
        return None, 0.0, {}
    if (
        structural.confidence > 0
        and structural.kind != suggested
        and structural.winning_tier in {SignalTier.PROPERTIES, SignalTier.ANATOMY}
        and structural.confidence >= ctx.grey_zone_min
    ):
        return None, 0.0, {}
    return (
        suggested,
        hint.confidence,
        {"source": "llm_hint", "structural_runner_up": structural.kind.value},
    )


def _maybe_llm_hint(
    ctx: DetectorContext,
) -> tuple[WidgetIrKind | None, float, dict[str, object], KindPayload | None]:
    hint = ctx.llm_hint
    if hint is None or hint.confidence < ctx.confidence_threshold:
        return None, 0.0, {}, None
    suggested = WidgetIrKind(hint.suggested_kind)
    if suggested in ctx.signals.hard_reject_kinds:
        return None, 0.0, {}, None
    if suggested in _OVERLAY_KINDS and not ctx.signals.overlay_signal:
        return None, 0.0, {}, None
    payload = payload_for_kind(suggested, ir_node=ctx.ir_node)
    return (
        suggested,
        hint.confidence,
        {"source": "llm_hint_only"},
        payload,
    )
