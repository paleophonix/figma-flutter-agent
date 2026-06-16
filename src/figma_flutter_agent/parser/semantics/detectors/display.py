"""Container and media semantic detectors."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.detectors._base import (
    RuleDetector,
    _child_types,
    _extent,
    _is_compact_square,
    _positive_extent,
    _signal_type,
    _variant_axis_value,
)
from figma_flutter_agent.parser.semantics.models import DetectorContext, SignalTier
from figma_flutter_agent.schemas import NodeType, WidgetIrKind


def _is_container_card(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    from figma_flutter_agent.parser.interaction.icons import passive_decorative_icon_glyph

    if passive_decorative_icon_glyph(node):
        return False
    signal_type = _signal_type(node)
    return signal_type == NodeType.CARD or (
        signal_type == NodeType.CONTAINER
        and bool(node.style.background_color or node.style.border_color)
        and len(node.children) >= 1
    )


def _is_list_tile(ctx: DetectorContext) -> bool:
    hits = ctx.signals.anatomy_hits
    if hits.get("list_tile_shape"):
        return True
    node = ctx.clean_node
    if node.type not in {NodeType.ROW, NodeType.STACK} or len(node.children) < 2:
        return False
    types = _child_types(node)
    return (NodeType.IMAGE in types or NodeType.VECTOR in types) and NodeType.TEXT in types


def _is_container_grid(ctx: DetectorContext) -> bool:
    return ctx.clean_node.type == NodeType.GRID


def _is_container_carousel(ctx: DetectorContext) -> bool:
    return ctx.clean_node.type == NodeType.CAROUSEL


def _is_container_accordion(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "variant")
    if axis and "accordion" in axis:
        return True
    node = ctx.clean_node
    if node.type != NodeType.COLUMN or len(node.children) < 2:
        return False
    from figma_flutter_agent.generator.ir.passes.sectionize import is_sectionize_band_wrapper_id

    if any(is_sectionize_band_wrapper_id(child.id) for child in node.children):
        return False
    if node.scroll_axis == "vertical":
        return False
    return _count_expandable(node) >= 2


def _count_expandable(node) -> int:
    from figma_flutter_agent.generator.ir.passes.sectionize import is_sectionize_band_wrapper_id

    return sum(
        1
        for child in node.children
        if not is_sectionize_band_wrapper_id(child.id)
        and child.type in {NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}
        and len(child.children) >= 2
    )


def _is_media_avatar(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    axis = _variant_axis_value(node, "type", "role")
    if axis and "avatar" in axis:
        return True
    if node.type not in {NodeType.IMAGE, NodeType.VECTOR, NodeType.CONTAINER, NodeType.STACK}:
        return False
    if not _is_compact_square(node, max_side=80.0):
        return False
    extent = _positive_extent(node)
    if extent is None:
        return False
    width, height = extent
    return 0.85 <= width / height <= 1.15


def _is_media_badge(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    axis = _variant_axis_value(node, "type", "role")
    if axis and "badge" in axis:
        return True
    width, height = _extent(node)
    if width is None or height is None:
        return False
    return max(width, height) <= 28.0 and node.type in {
        NodeType.CONTAINER,
        NodeType.STACK,
        NodeType.TEXT,
    }


def _is_technical_divider(ctx: DetectorContext) -> bool:
    hits = ctx.signals.geometry_hits
    if hits.get("divider_like"):
        return True
    node = ctx.clean_node
    width, height = _extent(node)
    if width is None or height is None:
        return False
    return (
        height <= 4.0
        and width >= 24.0
        and node.type in {NodeType.VECTOR, NodeType.CONTAINER, NodeType.ROW}
    )


DISPLAY_DETECTORS: tuple[RuleDetector, ...] = (
    RuleDetector(
        WidgetIrKind.CONTAINER_CARD,
        predicate=_is_container_card,
        tier=SignalTier.ANATOMY,
        base_confidence=0.86,
        evidence_key="container_card",
    ),
    RuleDetector(
        WidgetIrKind.CONTAINER_LIST_TILE,
        predicate=_is_list_tile,
        tier=SignalTier.ANATOMY,
        base_confidence=0.84,
        evidence_key="container_list_tile",
    ),
    RuleDetector(
        WidgetIrKind.CONTAINER_GRID,
        predicate=_is_container_grid,
        tier=SignalTier.ANATOMY,
        base_confidence=0.9,
        evidence_key="container_grid",
    ),
    RuleDetector(
        WidgetIrKind.CONTAINER_CAROUSEL,
        predicate=_is_container_carousel,
        tier=SignalTier.ANATOMY,
        base_confidence=0.9,
        evidence_key="container_carousel",
    ),
    RuleDetector(
        WidgetIrKind.CONTAINER_ACCORDION,
        predicate=_is_container_accordion,
        tier=SignalTier.ANATOMY,
        base_confidence=0.82,
        evidence_key="container_accordion",
    ),
    RuleDetector(
        WidgetIrKind.MEDIA_AVATAR,
        predicate=_is_media_avatar,
        tier=SignalTier.GEOMETRY,
        base_confidence=0.78,
        evidence_key="media_avatar",
    ),
    RuleDetector(
        WidgetIrKind.MEDIA_BADGE,
        predicate=_is_media_badge,
        tier=SignalTier.GEOMETRY,
        base_confidence=0.76,
        evidence_key="media_badge",
    ),
    RuleDetector(
        WidgetIrKind.TECHNICAL_DIVIDER,
        predicate=_is_technical_divider,
        tier=SignalTier.ANATOMY,
        base_confidence=0.82,
        evidence_key="technical_divider",
    ),
)
