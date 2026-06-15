"""Shared detector helpers (structure-only, no layer names)."""

from __future__ import annotations

from collections.abc import Callable

from figma_flutter_agent.parser.semantics.models import Classification, DetectorContext, SignalTier
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrKind


def _extent(node: CleanDesignTreeNode) -> tuple[float | None, float | None]:
    width = node.sizing.width
    height = node.sizing.height
    if width is None and node.stack_placement is not None:
        width = node.stack_placement.width
    if height is None and node.stack_placement is not None:
        height = node.stack_placement.height
    return width, height


def _positive_extent(node: CleanDesignTreeNode) -> tuple[float, float] | None:
    """Return width and height when both are present and strictly positive."""
    width, height = _extent(node)
    if width is None or height is None:
        return None
    if width <= 0 or height <= 0:
        return None
    return float(width), float(height)


def _variant_axis_value(node: CleanDesignTreeNode, *axes: str) -> str | None:
    variant = node.variant
    if variant is None:
        return None
    wanted = {axis.lower() for axis in axes}
    for key, value in variant.variant_properties.items():
        if key.lower() in wanted:
            return str(value).lower()
    return None


def _signal_type(node: CleanDesignTreeNode) -> NodeType:
    from figma_flutter_agent.parser.semantics.signals.type_trust import semantic_signal_type

    return semantic_signal_type(node)


def _child_types(node: CleanDesignTreeNode) -> set[NodeType]:
    return {_signal_type(child) for child in node.children}


def _has_filled_surface(node: CleanDesignTreeNode) -> bool:
    return bool(node.style.background_color)


def _has_outlined_surface(node: CleanDesignTreeNode) -> bool:
    return bool(node.style.border_color) and not _has_filled_surface(node)


def _is_compact_square(node: CleanDesignTreeNode, *, max_side: float = 64.0) -> bool:
    extent = _positive_extent(node)
    if extent is None:
        return False
    width, height = extent
    return max(width, height) <= max_side and abs(width - height) <= 8.0


def _count_type(node: CleanDesignTreeNode, node_type: NodeType) -> int:
    return sum(1 for child in node.children if _signal_type(child) == node_type)


class RuleDetector:
    """Rule-based detector with tier-aware confidence."""

    def __init__(
        self,
        kind: WidgetIrKind,
        *,
        predicate: Callable[[DetectorContext], bool],
        tier: SignalTier,
        base_confidence: float,
        evidence_key: str,
    ) -> None:
        self.kind = kind
        self._predicate = predicate
        self._tier = tier
        self._base_confidence = base_confidence
        self._evidence_key = evidence_key

    def detect(self, ctx: DetectorContext) -> Classification | None:
        if not self._predicate(ctx):
            return None
        tier_score = {
            SignalTier.PROPERTIES: ctx.signals.properties_score,
            SignalTier.ANATOMY: ctx.signals.anatomy_score,
            SignalTier.GEOMETRY: ctx.signals.geometry_score,
        }[self._tier]
        confidence = max(self._base_confidence, tier_score)
        if self._tier == SignalTier.PROPERTIES and ctx.signals.property_hits:
            confidence = max(confidence, 0.85)
        return Classification(
            kind=self.kind,
            confidence=min(confidence, 1.0),
            winning_tier=self._tier,
            evidence={self._evidence_key: True},
        )
