"""Tier-3 geometry signals."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.models import TierSignals
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _extent(node: CleanDesignTreeNode) -> tuple[float | None, float | None]:
    width = node.sizing.width
    height = node.sizing.height
    if width is None and node.stack_placement is not None:
        width = node.stack_placement.width
    if height is None and node.stack_placement is not None:
        height = node.stack_placement.height
    return width, height


def collect_geometry_signals(node: CleanDesignTreeNode) -> TierSignals:
    """Collect tier-3 geometry heuristics."""
    hits: dict[str, object] = {}
    score = 0.0
    width, height = _extent(node)
    if width is not None and height is not None and width > 0 and height > 0:
        aspect = width / height
        hits["aspect_ratio"] = round(aspect, 3)
        if 0.85 <= aspect <= 1.15 and min(width, height) <= 80:
            score = max(score, 0.65)
            hits["square_compact"] = True
        if aspect >= 3.0 and height <= 64:
            score = max(score, 0.6)
            hits["horizontal_bar"] = True

    if node.scroll_axis == "vertical":
        score = max(score, 0.7)
        hits["scroll_axis"] = "vertical"

    if node.type == NodeType.VECTOR and node.style.has_stroke and height and height <= 4:
        score = max(score, 0.75)
        hits["divider_like"] = True

    return TierSignals(geometry_score=min(score, 1.0), geometry_hits=hits)
