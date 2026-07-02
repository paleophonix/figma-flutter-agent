"""Stack-specific flex policies."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.geometry_facts import (
    CARD_HERO_MIN_HEIGHT,
    CARD_HERO_MIN_HEIGHT_RATIO,
    CARD_HERO_MIN_WIDTH,
    CARD_METADATA_STACK_MAX_HEIGHT,
    CARD_METADATA_STACK_MAX_WIDTH,
    CARD_METADATA_STACK_MIN_HEIGHT,
    CIRCULAR_OPTION_MAX_EXTENT,
    CIRCULAR_OPTION_MIN_EXTENT,
    SMALL_VECTOR_MAX_EXTENT,
    STACK_PANEL_MIN_HEIGHT,
    SUBTITLE_LINE_MAX_HEIGHT,
    SUBTITLE_STACK_STRUT_BUFFER,
    viewport_chrome_band_size,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    round_geometry,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_GROWABLE_PANEL_MICRO_OVERLAP_TOLERANCE_PX = 4.0


def _viewport_chrome_vertical_role(child: CleanDesignTreeNode) -> str | None:
    """Resolve TOP/BOTTOM chrome role when Figma omits ``placement.vertical``."""
    if not is_viewport_chrome_band(child):
        return None
    placement = child.stack_placement
    if placement is not None and placement.vertical in {"TOP", "BOTTOM"}:
        return placement.vertical
    name = (child.name or "").lower()
    if "status bar" in name:
        return "TOP"
    if "home indicator" in name:
        return "BOTTOM"
    return None


def is_viewport_chrome_band(node: CleanDesignTreeNode) -> bool:
    """Return True for full-bleed iOS/Android status and home-indicator chrome."""
    name = (node.name or "").strip()
    if name.startswith("Native /"):
        return True
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not viewport_chrome_band_size(width, height):
        return False
    placement = node.stack_placement
    if placement is None:
        return False
    return placement.vertical in {"TOP", "BOTTOM"}


def layout_fact_stack_positioned_subtitle_line(node: CleanDesignTreeNode) -> bool:
    """True for a single-line subtitle ``STACK`` with fractional pin offsets.

    Address and list cards often pin secondary copy inside a short stack.
    Binding the Figma frame height fights ``StrutStyle`` metrics and creates
    ``Column`` overflow in the parent spaced stack.
    """
    if node.type != NodeType.STACK or len(node.children) != 1:
        return False
    child = node.children[0]
    if child.type != NodeType.TEXT:
        return False
    placement = child.stack_placement
    if placement is None:
        return False
    line_height = placement.height
    if line_height is None or line_height <= 0:
        line_height = node.sizing.height
    if line_height is None or line_height > SUBTITLE_LINE_MAX_HEIGHT:
        return False
    if placement.vertical == "BOTTOM":
        return False
    return placement.bottom is not None or placement.top is not None


def subtitle_stack_bounded_height(node: CleanDesignTreeNode) -> float:
    """Return a finite cross-axis extent for a positioned subtitle ``STACK``.

    ``Stack`` children laid out with fractional ``top``/``bottom`` pins need a
    bounded parent. The raw Figma frame height is often shorter than Flutter
    ``StrutStyle`` metrics once pin insets are applied.
    """
    from figma_flutter_agent.generator.geometry.affine import geom_epsilon

    child = node.children[0]
    placement = child.stack_placement
    line_height = placement.height if placement and placement.height else None
    if line_height is None or line_height <= 0:
        line_height = node.sizing.height
    if line_height is None or line_height <= 0:
        line_height = child.sizing.height
    line_height = float(line_height or 21.0)
    top_inset = abs(float(placement.top)) if placement and placement.top is not None else 0.0
    bottom_inset = float(placement.bottom) if placement and placement.bottom is not None else 0.0
    extent = line_height + top_inset + bottom_inset + SUBTITLE_STACK_STRUT_BUFFER
    frame_height = node.sizing.height
    if frame_height is not None and float(frame_height) > extent:
        extent = float(frame_height)
    return round_geometry(max(extent, line_height + geom_epsilon()))


def wrap_subtitle_stack_sized_box(
    widget: str,
    node: CleanDesignTreeNode,
    *,
    width_lit: str,
) -> str:
    """Wrap a subtitle ``STACK`` with width and a strut-safe bounded height."""
    height_lit = format_geometry_literal(subtitle_stack_bounded_height(node))
    return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {widget})"


def stack_child_is_growable_panel(child: CleanDesignTreeNode) -> bool:
    """True when a stack child is a multi-row panel that should grow in flow layout."""
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        column_bounded_slot_should_grow,
    )

    if column_bounded_slot_should_grow(child):
        return True
    if child.type != NodeType.COLUMN or child.scroll_axis != "none":
        return False
    if len(child.children) < 2:
        return False
    height: float | None = None
    if child.stack_placement is not None:
        height = child.stack_placement.height
    if (height is None or height <= 0) and child.sizing.height is not None:
        height = child.sizing.height
    return height is not None and float(height) >= STACK_PANEL_MIN_HEIGHT


def stack_child_overlaps_sibling_dashboard_card_region(
    child: CleanDesignTreeNode,
    parent_stack: CleanDesignTreeNode,
) -> bool:
    """Return True when a growable panel intersects a pinned dashboard card sibling."""
    from figma_flutter_agent.parser.interaction.absolute_fields import (
        layout_fact_painted_dashboard_card_shell,
        painted_dashboard_card_vertical_span,
    )

    if not stack_child_is_growable_panel(child):
        return False
    child_top = stack_child_ordinal_top(child)
    child_bottom = stack_child_ordinal_bottom(child)
    for sibling in parent_stack.children:
        if sibling.id == child.id or not layout_fact_painted_dashboard_card_shell(sibling):
            continue
        card_span = painted_dashboard_card_vertical_span(sibling)
        if card_span is None:
            continue
        card_top, card_bottom = card_span
        if child_top < card_bottom - 1.0 and child_bottom > card_top + 1.0:
            return True
    return False


def _stack_flow_body_children(stack: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Return stack siblings that participate in shared body scroll (exclude docked chrome)."""
    from figma_flutter_agent.generator.layout.stack_chrome import (
        is_bottom_docked_stack_child,
    )

    body_children: list[CleanDesignTreeNode] = []
    for child in stack.children:
        if is_bottom_docked_stack_child(child) or is_viewport_chrome_band(child):
            continue
        placement = child.stack_placement
        if placement is not None and placement.vertical == "BOTTOM":
            continue
        body_children.append(child)
    return body_children


def stack_uses_shared_body_scroll_host(
    stack: CleanDesignTreeNode,
    *,
    growable_panels: int | None = None,
) -> bool:
    """Law: single_scroll_host_per_screen_region for multi-panel bottom-chrome shells."""
    from figma_flutter_agent.generator.layout.widgets.positioned import (
        _stack_has_bottom_anchored_child,
    )

    if stack.type != NodeType.STACK or not _stack_has_bottom_anchored_child(stack):
        return False
    body_children = _stack_flow_body_children(stack)
    if growable_panels is None:
        growable_panels = sum(1 for child in body_children if stack_child_is_growable_panel(child))
    if growable_panels < 2:
        return False
    growable_body = [child for child in body_children if stack_child_is_growable_panel(child)]
    if len(growable_body) < 2:
        return False
    return tree_children_are_vertically_sequential(
        growable_body,
        overlap_tolerance_px=_GROWABLE_PANEL_MICRO_OVERLAP_TOLERANCE_PX,
    )


def stack_flow_child_is_shared_scroll_body(
    child: CleanDesignTreeNode,
    parent_stack: CleanDesignTreeNode,
) -> bool:
    """True when a stack slot belongs in the shared body scroll region."""
    from figma_flutter_agent.generator.layout.stack_chrome import (
        is_bottom_docked_stack_child,
    )

    if is_bottom_docked_stack_child(child) or is_viewport_chrome_band(child):
        return False
    if stack_child_overlaps_sibling_dashboard_card_region(child, parent_stack):
        return False
    return stack_child_is_growable_panel(child)


def stack_flow_column_child_sort_key(child: CleanDesignTreeNode) -> tuple[int, float, str]:
    """Order flow-column stack slots: body top-to-bottom, then bottom-docked chrome."""
    from figma_flutter_agent.generator.layout.stack_chrome import (
        is_bottom_docked_stack_child,
    )

    tier = 1 if is_bottom_docked_stack_child(child) else 0
    return (tier, stack_child_ordinal_top(child), child.id)


def stack_child_should_use_pin_bottom_scroll_host(
    child: CleanDesignTreeNode,
    *,
    parent_stack: CleanDesignTreeNode | None = None,
) -> bool:
    """True when pin-bottom-chrome flow should wrap this slot in a scroll host."""
    if not stack_child_is_growable_panel(child):
        return False
    if parent_stack is not None and stack_child_overlaps_sibling_dashboard_card_region(
        child, parent_stack
    ):
        return False
    if parent_stack is not None and stack_uses_shared_body_scroll_host(parent_stack):
        return False
    return True


def stack_child_should_suppress_inner_positioned_for_pin_bottom_scroll(
    child: CleanDesignTreeNode,
) -> bool:
    """True when a pin-bottom scroll host owns positioning (avoid ``ScrollView > Positioned``).

    PinBottomScrollHostLaw: the outer ``Positioned`` + ``SingleChildScrollView`` from
    ``pin_bottom_scroll_layer_expr`` already owns stack placement; the scroll child must
    emit layout content only (no nested ``Positioned``).
    """
    return stack_child_should_use_pin_bottom_scroll_host(child)


def stack_child_should_emit_positioned(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """Return True when a ``Positioned`` wrapper is valid for this node under its parent."""
    if parent_type not in {NodeType.STACK, NodeType.BUTTON}:
        return False
    if parent_node is not None and parent_type == NodeType.BUTTON:
        from figma_flutter_agent.generator.layout.flex_policy.buttons import (
            button_is_pill_with_centered_label,
        )
        from figma_flutter_agent.parser.interaction.buttons import (
            button_compiles_body_as_flex_row,
        )

        if button_compiles_body_as_flex_row(parent_node):
            return False
        if button_is_pill_with_centered_label(parent_node) and node.type == NodeType.TEXT:
            return False
    if parent_node is not None and parent_node.type == NodeType.STACK:
        from figma_flutter_agent.generator.layout.flex_policy.row import (
            layout_fact_stack_tab_switcher_host,
        )

        if layout_fact_stack_tab_switcher_host(parent_node):
            return False
        if stack_should_flow_as_column(parent_node):
            return False
        if stack_should_emit_mixed_inflow_column_overlay(parent_node):
            return stack_child_is_absolute_overlay(node)
        if stack_should_flow_as_centered_wrap(parent_node):
            return False
    return True


def stack_flow_child_known_height(child: CleanDesignTreeNode) -> float | None:
    """Return a stack flow slot's fixed Figma height when known."""
    placement = child.stack_placement
    height: float | None = None
    if placement is not None and placement.height is not None and placement.height > 0:
        height = float(placement.height)
    if (height is None or height <= 0) and child.sizing.height is not None:
        sizing_height = float(child.sizing.height)
        if sizing_height > 0:
            height = sizing_height
    return height


def stack_flow_child_needs_vertical_extent_bind(
    child: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
    responsive_enabled: bool = True,
) -> bool:
    """True when a non-growing flow slot needs a bounded height before scroll hosts.

    Args:
        child: Candidate stack flow slot.
        parent_node: Optional parent stack hosting the flow column.
        responsive_enabled: When false, intrinsic flow columns keep natural height.
    """
    _ = parent_node
    if stack_child_is_growable_panel(child):
        return False
    if (
        not responsive_enabled
        and child.type == NodeType.STACK
        and stack_should_flow_as_column(child)
    ):
        return False
    return stack_flow_child_known_height(child) is not None


def stack_child_is_positioned_only_stack(node: CleanDesignTreeNode) -> bool:
    """True when a stack hosts only absolutely positioned children."""
    if node.type != NodeType.STACK or not node.children:
        return False
    return all(child.stack_placement is not None for child in node.children)


def card_has_edge_to_edge_hero_stack(node: CleanDesignTreeNode) -> bool:
    """Product tiles with a full-width image hero above a padded metadata column."""
    if node.type != NodeType.CARD or len(node.children) < 2:
        return False
    hero = node.children[0]
    meta = node.children[1]
    if hero.type != NodeType.STACK or meta.type != NodeType.COLUMN:
        return False
    hero_width = hero.sizing.width
    hero_height = hero.sizing.height
    card_height = node.sizing.height
    if (
        hero_width is None
        or hero_height is None
        or card_height is None
        or float(hero_width) < CARD_HERO_MIN_WIDTH
        or float(hero_height) < CARD_HERO_MIN_HEIGHT
    ):
        return False
    return float(hero_height) / float(card_height) >= CARD_HERO_MIN_HEIGHT_RATIO


_CARD_HERO_INSET_WIDTH_EPSILON = 1.0


def card_has_inset_hero_media_frame(node: CleanDesignTreeNode) -> bool:
    """True when a product-tile hero is narrower than the card shell (inset media)."""
    if not card_has_edge_to_edge_hero_stack(node):
        return False
    hero = node.children[0]
    card_width = node.sizing.width
    hero_width = hero.sizing.width
    if card_width is None or hero_width is None or float(card_width) <= 0:
        return False
    return float(hero_width) < float(card_width) - _CARD_HERO_INSET_WIDTH_EPSILON


def card_child_is_product_tile_metadata_slot(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """True when ``node`` is the metadata column under a product-tile card."""
    if parent_node is None or parent_node.type != NodeType.CARD:
        return False
    if len(parent_node.children) < 2:
        return False
    if node.id != parent_node.children[1].id:
        return False
    return card_has_edge_to_edge_hero_stack(parent_node)


def _is_compact_dimension_label(text: str) -> bool:
    """Return True for short numeric or apparel-size labels on circular option chips."""
    stripped = text.strip()
    if not stripped or len(stripped) > 6:
        return False
    if stripped.isdigit():
        return True
    if stripped[0].isdigit():
        return True
    return stripped.upper() in {"S", "M", "L", "XS", "XL", "XXL"}


def layout_fact_stack_circular_option_glyph_host(node: CleanDesignTreeNode) -> bool:
    """Return True for square option chips with a fill surface and centered label overlay."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return False
    extent_w = float(width)
    extent_h = float(height)
    if (
        extent_w < CIRCULAR_OPTION_MIN_EXTENT
        or extent_h < CIRCULAR_OPTION_MIN_EXTENT
        or extent_w > CIRCULAR_OPTION_MAX_EXTENT
        or extent_h > CIRCULAR_OPTION_MAX_EXTENT
    ):
        return False
    if abs(extent_w - extent_h) > 4.0:
        return False
    from figma_flutter_agent.parser.interaction.shared import (
        _MAX_LOCAL_DEPTH,
        _local_nodes,
    )

    text_nodes = [
        item
        for item in _local_nodes(node, _MAX_LOCAL_DEPTH)
        if item.type == NodeType.TEXT and (item.text or "").strip()
    ]
    if len(text_nodes) != 1:
        return False
    if not _is_compact_dimension_label(text_nodes[0].text or ""):
        return False
    has_surface = any(
        child.type in {NodeType.CONTAINER, NodeType.VECTOR, NodeType.STACK}
        and (
            child.style.background_color
            or (
                child.sizing.width is not None
                and child.sizing.height is not None
                and float(child.sizing.width) >= extent_w * 0.85
                and float(child.sizing.height) >= extent_h * 0.85
            )
        )
        for child in node.children
        if child.type != NodeType.TEXT
    )
    return has_surface


_ICON_BADGE_STACK_MAX_EXTENT = 64.0


def _icon_badge_stack_has_glyph(child: CleanDesignTreeNode) -> bool:
    """Return True when a stack child carries an exportable vector glyph."""
    if child.type in {NodeType.VECTOR, NodeType.IMAGE} and (
        child.vector_asset_key or child.image_asset_key
    ):
        return True
    if child.vector_asset_key or child.image_asset_key:
        return True
    from figma_flutter_agent.parser.interaction.icons import (
        _BACK_NAV_DESCENDANT_DEPTH,
        _descendant_nodes,
        _stack_has_vector_icon,
    )

    return _stack_has_vector_icon(_descendant_nodes(child, _BACK_NAV_DESCENDANT_DEPTH))


def layout_fact_icon_badge_stack(node: CleanDesignTreeNode) -> bool:
    """Return True for compact filled-surface stacks with a centered vector glyph."""
    if node.type != NodeType.STACK:
        return False
    if layout_fact_stack_circular_option_glyph_host(node):
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return False
    if float(width) > _ICON_BADGE_STACK_MAX_EXTENT or float(height) > _ICON_BADGE_STACK_MAX_EXTENT:
        return False
    has_fill_surface = False
    has_glyph = False
    text_labels = 0
    for child in node.children:
        if child.type == NodeType.TEXT and (child.text or "").strip():
            text_labels += 1
        if child.type == NodeType.CONTAINER and (
            child.style.background_color or child.style.has_stroke
        ):
            has_fill_surface = True
        if _icon_badge_stack_has_glyph(child):
            has_glyph = True
    if node.style.background_color or node.style.has_stroke:
        has_fill_surface = True
    return text_labels == 0 and has_fill_surface and has_glyph


def stack_should_emit_as_metadata_column(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """True when a narrow card stack should flow as ``Column`` instead of ``Stack``."""
    from figma_flutter_agent.schemas import WrapKind

    if not layout_fact_stack_card_metadata_host(node, parent_node=parent_node):
        return False
    slot = node.layout_slot
    if slot is not None and WrapKind.CONSTRAINED_BOX in slot.wraps:
        return any(child.stack_placement is not None for child in node.children)
    return True


def layout_fact_stack_card_metadata_host(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """True for narrow card stacks that host timestamps and optional badges."""
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_card_composite_body,
    )
    from figma_flutter_agent.generator.layout.widgets.svg import (
        _should_center_in_parent_stack,
    )

    if node.type != NodeType.STACK:
        return False
    if layout_fact_stack_circular_option_glyph_host(node):
        return False
    width = node.sizing.width
    if width is None or width <= 0 or width > CARD_METADATA_STACK_MAX_WIDTH:
        return False
    if any(_should_center_in_parent_stack(child, node) for child in node.children):
        return False
    height = node.sizing.height
    if height is not None and height > 0:
        if CARD_METADATA_STACK_MIN_HEIGHT <= float(height) <= CARD_METADATA_STACK_MAX_HEIGHT:
            if len(node.children) >= 2 and not tree_children_are_vertically_sequential(
                node.children
            ):
                return False
            return True
    if parent_node is not None and layout_fact_row_card_composite_body(parent_node):
        return True
    return False


def _is_notification_dot_badge(node: CleanDesignTreeNode) -> bool:
    """Small absolute colored vector dot used as a notification badge without a count."""
    if node.type not in {NodeType.STACK, NodeType.CONTAINER, NodeType.ROW}:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if float(width) > 20.0 or float(height) > 22.0:
        return False
    if node.stack_placement is None:
        return False
    for child in node.children:
        if child.type != NodeType.VECTOR:
            continue
        if not child.style.background_color:
            continue
        vector_width = child.sizing.width
        vector_height = child.sizing.height
        if vector_width is None or vector_height is None:
            continue
        if (
            float(vector_width) <= SMALL_VECTOR_MAX_EXTENT
            and float(vector_height) <= SMALL_VECTOR_MAX_EXTENT
        ):
            return True
    return False


def _stack_has_vector_export(node: CleanDesignTreeNode, *, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if node.vector_asset_key:
        return True
    return any(_stack_has_vector_export(child, depth=depth + 1) for child in node.children)


def stack_hosts_notification_badge_overlay(node: CleanDesignTreeNode) -> bool:
    """True when a compact icon stack also carries an absolutely positioned numeric badge."""
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_numeric_counter_badge,
    )

    if node.type != NodeType.STACK:
        return False
    if not _stack_has_vector_export(node):
        return False

    def walk_badge(current: CleanDesignTreeNode, depth: int = 0) -> bool:
        if depth > 5:
            return False
        if layout_fact_row_numeric_counter_badge(current) or _is_notification_dot_badge(current):
            return True
        for child in current.children:
            if walk_badge(child, depth=depth + 1):
                return True
        return False

    return walk_badge(node)


def layout_fact_stack_numeric_glyph_overlay_host(node: CleanDesignTreeNode) -> bool:
    """Return True for compact stack hosts carrying an oval/vector plus digit overlay."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return False
    if float(width) > SUBTITLE_LINE_MAX_HEIGHT or float(height) > SUBTITLE_LINE_MAX_HEIGHT:
        return False
    text_nodes = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]
    if len(text_nodes) != 1:
        return False
    glyph = (text_nodes[0].text or "").strip()
    if not glyph.isdigit() or len(glyph) > 3:
        return False
    has_vector = any(
        child.type == NodeType.VECTOR or child.vector_asset_key for child in node.children
    )
    return has_vector


_COMPACT_ICON_LABEL_METRIC_MAX_WIDTH = 96.0
_COMPACT_ICON_LABEL_METRIC_MAX_HEIGHT = 28.0


def _stack_child_horizontal_origin(child: CleanDesignTreeNode) -> float:
    """Return the horizontal origin of a stack child from placement or offset."""
    placement = child.stack_placement
    if placement is not None and placement.left is not None:
        return float(placement.left)
    return float(child.offset_x or 0.0)


def _stack_child_layout_width(child: CleanDesignTreeNode) -> float:
    """Return the horizontal extent of a stack child when known."""
    placement = child.stack_placement
    if placement is not None and placement.width is not None and placement.width > 0:
        return float(placement.width)
    if child.sizing.width is not None and child.sizing.width > 0:
        return float(child.sizing.width)
    return 0.0


def layout_fact_stack_compact_icon_label_metric(node: CleanDesignTreeNode) -> bool:
    """Compact icon+label stacks whose label would clip when absolutely placed."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return False
    if (
        float(width) > _COMPACT_ICON_LABEL_METRIC_MAX_WIDTH
        or float(height) > _COMPACT_ICON_LABEL_METRIC_MAX_HEIGHT
    ):
        return False
    if layout_fact_stack_numeric_glyph_overlay_host(node):
        return False
    text_nodes = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]
    icon_nodes = [
        child
        for child in node.children
        if child.type in {NodeType.VECTOR, NodeType.IMAGE}
        or child.vector_asset_key
        or child.image_asset_key
    ]
    if len(text_nodes) != 1 or not icon_nodes:
        return False
    text = text_nodes[0]
    icon = icon_nodes[0]
    text_left = _stack_child_horizontal_origin(text)
    icon_right = _stack_child_horizontal_origin(icon) + _stack_child_layout_width(icon)
    text_width = _stack_child_layout_width(text)
    frame_width = float(width)
    if text_left < icon_right + 1.0:
        return True
    if text_width > 0 and text_left + text_width > frame_width + 0.5:
        return True
    return len(node.children) == 2


_METRIC_BAND_Y_TOLERANCE_PX = 4.0
_METRIC_BAND_MIN_CHILDREN = 2
_METRIC_BAND_MAX_CHILDREN = 4


def layout_fact_stack_metric_icon_label_band(node: CleanDesignTreeNode) -> bool:
    """Horizontal band of compact icon+label metric stacks sharing one Y row."""
    if node.type != NodeType.STACK:
        return False
    metric_children = [
        child for child in node.children if layout_fact_stack_compact_icon_label_metric(child)
    ]
    if not (_METRIC_BAND_MIN_CHILDREN <= len(metric_children) <= _METRIC_BAND_MAX_CHILDREN):
        return False
    if len(metric_children) != len(node.children):
        return False
    tops = [stack_child_ordinal_top(child) for child in metric_children]
    if max(tops) - min(tops) > _METRIC_BAND_Y_TOLERANCE_PX:
        return False
    lefts = [stack_child_ordinal_left(child) for child in metric_children]
    return lefts == sorted(lefts)


def stack_metadata_timestamp_host(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """True when a stack child is the timestamp row above a notification badge."""
    if parent_node is None or parent_node.type != NodeType.STACK:
        return False
    width = parent_node.sizing.width
    if width is None or width <= 0 or width > CARD_METADATA_STACK_MAX_WIDTH:
        return False
    if node.type == NodeType.TEXT:
        return True
    if node.type == NodeType.COLUMN and len(node.children) == 1:
        return node.children[0].type == NodeType.TEXT
    return False


def _geometry_frame_ordinal_top(child: CleanDesignTreeNode) -> float | None:
    """Return a parent-relative Y ordinal from the geometry contract when present."""
    frame = child.geometry_frame
    if frame is None:
        return None
    if frame.layout_rect is not None and frame.layout_rect.y is not None:
        return float(frame.layout_rect.y)
    if frame.placement_origin is not None:
        return float(frame.placement_origin.y)
    return None


def stack_child_ordinal_top(child: CleanDesignTreeNode) -> float:
    """Return a stack child's vertical ordinal for metadata column ordering."""
    if child.stack_placement is not None and child.stack_placement.top is not None:
        return float(child.stack_placement.top)
    geometry_top = _geometry_frame_ordinal_top(child)
    if geometry_top is not None:
        return geometry_top
    return float(child.offset_y or 0.0)


def stack_child_ordinal_bottom(child: CleanDesignTreeNode) -> float:
    """Return a stack child's bottom edge from Figma placement or sizing."""
    frame = child.geometry_frame
    if frame is not None and frame.layout_rect is not None:
        layout_rect = frame.layout_rect
        layout_top = float(layout_rect.y or 0.0)
        layout_height = float(layout_rect.height or 0.0)
        if layout_height > 0:
            return layout_top + layout_height
    top = stack_child_ordinal_top(child)
    height: float | None = None
    if child.stack_placement is not None and child.stack_placement.height is not None:
        height = float(child.stack_placement.height)
    if (
        (height is None or height <= 0)
        and child.sizing.height is not None
        and child.sizing.height > 0
    ):
        height = float(child.sizing.height)
    return top + float(height or 0.0)


def tree_children_are_vertically_sequential(
    children: list[CleanDesignTreeNode],
    *,
    overlap_tolerance_px: float = 0.0,
) -> bool:
    """True when siblings do not overlap on the vertical axis.

    Args:
        children: Siblings to compare in top-to-bottom order.
        overlap_tolerance_px: Allowed micro-overlap between adjacent panels from
            Figma placement rounding (shared-scroll growable batching only).
    """
    if len(children) < 2:
        return False
    tolerance = max(0.0, float(overlap_tolerance_px))
    ordered = sorted(
        children,
        key=lambda child: (stack_child_ordinal_top(child), child.id),
    )
    for previous, current in zip(ordered, ordered[1:], strict=False):
        previous_top = stack_child_ordinal_top(previous)
        current_top = stack_child_ordinal_top(current)
        if abs(current_top - previous_top) < 0.5:
            return False
        if current_top < stack_child_ordinal_bottom(previous) - tolerance - 0.5:
            return False
    return True


def stack_children_are_vertically_sequential(stack: CleanDesignTreeNode) -> bool:
    """True when positioned stack children do not overlap on the vertical axis."""
    if stack.type != NodeType.STACK:
        return False
    return tree_children_are_vertically_sequential(stack.children)


def _stack_is_title_subtitle_text_block(stack: CleanDesignTreeNode) -> bool:
    """True when a stack hosts single-line text columns in vertical order."""
    if stack.type != NodeType.STACK or len(stack.children) < 2:
        return False
    text_slots = 0
    for child in stack.children:
        if child.type != NodeType.COLUMN:
            continue
        texts = [
            item
            for item in child.children
            if item.type == NodeType.TEXT and item.text and item.text.strip()
        ]
        if len(texts) == 1:
            text_slots += 1
    return text_slots >= 2


def _stack_is_phone_shell_layout(
    stack: CleanDesignTreeNode,
    *,
    growable_panels: int,
) -> bool:
    """True for status bar + scrollable body + home-indicator phone shells."""
    if stack.type != NodeType.STACK:
        return False
    return _children_form_phone_shell_layout(stack.children, growable_panels=growable_panels)


def _column_is_phone_shell_layout(
    column: CleanDesignTreeNode,
    *,
    growable_panels: int,
) -> bool:
    """True when a decomposed ``COLUMN`` root mirrors a phone chrome shell."""
    if column.type != NodeType.COLUMN:
        return False
    return _children_form_phone_shell_layout(column.children, growable_panels=growable_panels)


def _children_form_phone_shell_layout(
    children: list[CleanDesignTreeNode],
    *,
    growable_panels: int,
) -> bool:
    """True when ordered children include top chrome, growable body, and bottom chrome."""
    if growable_panels < 1:
        return False
    has_top_chrome = False
    has_bottom_chrome = False
    for child in children:
        role = _viewport_chrome_vertical_role(child)
        if role == "TOP":
            has_top_chrome = True
        elif role == "BOTTOM":
            has_bottom_chrome = True
    return has_top_chrome and has_bottom_chrome


def stack_child_is_absolute_overlay(child: CleanDesignTreeNode) -> bool:
    """True when a stack child is absolutely positioned relative to its stack host."""
    if child.stack_placement is not None:
        return True
    return child.layout_positioning == "ABSOLUTE"


def stack_should_emit_mixed_inflow_column_overlay(stack: CleanDesignTreeNode) -> bool:
    """True when in-flow siblings must ``Column``-flow inside a ``Stack`` with absolute overlays.

    Mixed auto-layout stacks keep AUTO/in-flow children in document order while one or more
    ABSOLUTE siblings (for example decorative backgrounds) retain ``Positioned`` slots. Bare
    in-flow children in a ``Stack`` collapse to the origin and overlap.
    """
    from figma_flutter_agent.parser.semantics.signals.chip_anatomy import (
        is_tag_option_chip_group,
        stack_should_preserve_absolute_tag_chips,
    )

    if stack.type != NodeType.STACK or len(stack.children) < 2:
        return False
    if stack_should_flow_as_column(stack):
        return False
    if stack_has_non_sequential_raster_overlay(stack):
        return False
    if is_tag_option_chip_group(stack) or stack_should_preserve_absolute_tag_chips(stack):
        return False
    inflow = [child for child in stack.children if not stack_child_is_absolute_overlay(child)]
    absolute = [child for child in stack.children if stack_child_is_absolute_overlay(child)]
    if not inflow or not absolute:
        return False
    if len(inflow) < 2 and (stack.spacing or 0.0) <= 0.0:
        return False
    return tree_children_are_vertically_sequential(inflow)


def stack_should_emit_coalesced_inflow_fallback(stack: CleanDesignTreeNode) -> bool:
    """Emit one inflow ``Column`` when absolute decor blocked mixed-inflow routing."""
    if stack_should_emit_mixed_inflow_column_overlay(stack):
        return False
    if stack.type != NodeType.STACK or len(stack.children) < 2:
        return False
    inflow = [child for child in stack.children if not stack_child_is_absolute_overlay(child)]
    absolute = [child for child in stack.children if stack_child_is_absolute_overlay(child)]
    if not inflow or not absolute:
        return False
    if len(inflow) < 2 and (stack.spacing or 0.0) <= 0.0:
        return False
    return True


def stack_should_emit_surface_decoration(
    stack: CleanDesignTreeNode,
    *,
    is_layout_root: bool,
) -> bool:
    """Return True when a stack host should emit painted card/chrome decoration."""
    if is_layout_root:
        return True
    style = stack.style
    if style.background_color is not None:
        return True
    if style.border_radius is not None and float(style.border_radius) > 0.0:
        return True
    if style.border_color is not None:
        return True
    return False


def stack_has_non_sequential_raster_overlay(stack: CleanDesignTreeNode) -> bool:
    """Return True when a raster photo overlaps siblings and blocks column flow."""
    from figma_flutter_agent.generator.ir.passes.geometry import (
        stack_children_overlap_on_y,
    )
    from figma_flutter_agent.parser.interaction import find_raster_photo_leaf

    raster = find_raster_photo_leaf(stack)
    if raster is None:
        return False
    from figma_flutter_agent.parser.interaction.enrichment import (
        layout_fact_decorative_blur_absolute_overlay,
    )

    if layout_fact_decorative_blur_absolute_overlay(raster):
        return False
    for child in stack.children:
        if child.id == raster.id:
            continue
        placement = child.stack_placement
        if placement is not None and placement.vertical == "BOTTOM":
            continue
        if stack_children_overlap_on_y(raster, child):
            return True
    return False


def stack_dense_absolute_overlays_preserve_stack(stack: CleanDesignTreeNode) -> bool:
    """Return True when dense absolute overlays must keep a fixed artboard as ``Stack``.

    AbsoluteOverlayDensityPreservationLaw: veto column lowering when positioned
    overlay slots outnumber growable panels on a non-sequential stack body.
    """
    if stack.type != NodeType.STACK:
        return False
    if stack_children_are_vertically_sequential(stack):
        return False
    if not stack_has_absolute_overlay_form_slots(stack):
        return False
    body_children = _stack_flow_body_children(stack)
    overlay_count = sum(
        1
        for child in body_children
        if child.stack_placement is not None and not stack_child_is_growable_panel(child)
    )
    growable_count = sum(1 for child in body_children if stack_child_is_growable_panel(child))
    return overlay_count > growable_count


def stack_has_absolute_overlay_form_slots(stack: CleanDesignTreeNode) -> bool:
    """Return True when absolute hero/card overlays must stay in ``Stack``, not flow ``Column``."""
    from figma_flutter_agent.generator.layout.stack_chrome import (
        is_bottom_docked_stack_child,
    )

    if stack.type != NodeType.STACK:
        return False
    body_children = [
        child
        for child in stack.children
        if not is_viewport_chrome_band(child) and not is_bottom_docked_stack_child(child)
    ]
    growable = [child for child in body_children if stack_child_is_growable_panel(child)]
    overlays = [child for child in body_children if child not in growable]
    if not growable or not overlays:
        return False
    return any(child.stack_placement is not None for child in overlays)


def stack_should_flow_as_column(stack: CleanDesignTreeNode) -> bool:
    """True when vertically stacked panels should grow in a ``Column`` instead of ``Stack``."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_stack_bottom_nav_tab_glyph_column,
    )
    from figma_flutter_agent.generator.layout.widgets.positioned import (
        _stack_has_bottom_anchored_child,
    )
    from figma_flutter_agent.parser.semantics.signals.chip_anatomy import (
        is_tag_option_chip_group,
        stack_should_preserve_absolute_tag_chips,
    )

    if layout_fact_stack_bottom_nav_tab_glyph_column(stack):
        return True

    if stack_has_non_sequential_raster_overlay(stack):
        return False

    if stack_dense_absolute_overlays_preserve_stack(stack):
        return False

    if stack_uses_shared_body_scroll_host(stack):
        return True

    if stack_has_absolute_overlay_form_slots(stack):
        return False

    if is_tag_option_chip_group(stack) or stack_should_preserve_absolute_tag_chips(stack):
        return False

    if stack.type != NodeType.STACK or len(stack.children) < 2:
        return False
    body_children = _stack_flow_body_children(stack)
    growable_panels = sum(1 for child in body_children if stack_child_is_growable_panel(child))
    if _stack_is_phone_shell_layout(stack, growable_panels=growable_panels):
        return True
    if stack_uses_shared_body_scroll_host(stack, growable_panels=growable_panels):
        return True
    if not stack_children_are_vertically_sequential(stack):
        return False
    if growable_panels >= 2:
        return True
    if growable_panels >= 1 and _stack_has_bottom_anchored_child(stack):
        return True
    return _stack_is_title_subtitle_text_block(stack)


def stack_child_is_pill_button(child: CleanDesignTreeNode) -> bool:
    """Return True when a stack child is a painted pill chip button."""
    from figma_flutter_agent.generator.layout.flex_policy.buttons import (
        button_is_pill_with_centered_label,
        button_should_fitted_box_label,
    )

    if child.type != NodeType.BUTTON:
        return False
    return button_is_pill_with_centered_label(child) or button_should_fitted_box_label(child)


def stack_child_ordinal_left(child: CleanDesignTreeNode) -> float:
    """Return a stack child's horizontal ordinal for wrap ordering."""
    if child.stack_placement is not None and child.stack_placement.left is not None:
        return float(child.stack_placement.left)
    return 0.0


def stack_pill_button_wrap_spacing(children: list[CleanDesignTreeNode]) -> float:
    """Derive horizontal chip gap from absolute stack placements."""
    default = 8.0
    rows: dict[int, list[tuple[float, float]]] = {}
    for child in children:
        placement = child.stack_placement
        if placement is None:
            continue
        top = round(float(placement.top or 0.0))
        left = stack_child_ordinal_left(child)
        width = float(placement.width or child.sizing.width or 0.0)
        if width <= 0:
            continue
        rows.setdefault(top, []).append((left, width))
    gaps: list[float] = []
    for row in rows.values():
        row.sort(key=lambda item: item[0])
        for index in range(1, len(row)):
            prev_left, prev_width = row[index - 1]
            cur_left, _ = row[index]
            gap = cur_left - (prev_left + prev_width)
            if gap > 0.5:
                gaps.append(gap)
    if not gaps:
        return default
    return round_geometry(min(gaps))


def stack_should_flow_as_centered_wrap(stack: CleanDesignTreeNode) -> bool:
    """True when pill chip buttons in a stack should emit as a centered ``Wrap``."""
    if stack.type != NodeType.STACK or len(stack.children) < 2:
        return False
    if not all(stack_child_is_pill_button(child) for child in stack.children):
        return False
    return all(child.stack_placement is not None for child in stack.children)


def _row_hosts_stack_flow_column_peer(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` pairs a fixed bbox with a flow-column ``Stack`` peer."""
    if node.type != NodeType.ROW:
        return False
    return any(
        child.type == NodeType.STACK and stack_should_flow_as_column(child)
        for child in node.children
    )


def _stack_flow_slot_prefers_min_height(
    child: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """True when a stack-flow slot should reserve ``minHeight`` instead of a fixed cap."""
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _column_is_text_primary,
        column_bounded_slot_should_grow,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_status_pill_badge,
    )
    from figma_flutter_agent.parser.interaction import button_should_flow_as_column

    if parent_node is not None and parent_node.type == NodeType.BUTTON:
        if button_should_flow_as_column(parent_node):
            return True
    if child.type == NodeType.BUTTON and button_should_flow_as_column(child):
        return True
    if column_bounded_slot_should_grow(child):
        return True
    if child.type == NodeType.ROW and layout_fact_row_status_pill_badge(child):
        return True
    if child.type == NodeType.COLUMN:
        if any(
            grand.type == NodeType.ROW and layout_fact_row_status_pill_badge(grand)
            for grand in child.children
        ):
            return True
        if _column_is_text_primary(child):
            return True
    return False


def stack_flow_child_horizontal_wrap(
    child: CleanDesignTreeNode,
    widget: str,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Stretch flow-column children that were horizontally pinned in Figma."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_stack_bottom_nav_tab_glyph_column,
    )

    if stack_child_is_absolute_overlay(child):
        return widget

    if parent_node is not None and layout_fact_stack_bottom_nav_tab_glyph_column(parent_node):
        width = child.sizing.width
        if width is not None and float(width) > 0:
            width_lit = format_geometry_literal(float(width))
            return (
                f"Align(alignment: Alignment.topCenter, "
                f"child: SizedBox(width: {width_lit}, child: {widget}))"
            )
    if is_viewport_chrome_band(child):
        width = child.sizing.width
        if width is not None and width > 0:
            width_lit = format_geometry_literal(float(width))
            align = (
                "Alignment.bottomCenter"
                if child.stack_placement is not None and child.stack_placement.vertical == "BOTTOM"
                else "Alignment.topCenter"
            )
            return (
                f"Align(alignment: {align}, child: SizedBox(width: {width_lit}, child: {widget}))"
            )
    placement = child.stack_placement
    if child.sizing.width_mode == SizingMode.FILL:
        return f"SizedBox(width: double.infinity, child: {widget})"
    if placement is not None:
        left = placement.left
        right = placement.right
        if left is not None and right is not None:
            return f"SizedBox(width: double.infinity, child: {widget})"
    return widget


def stack_flow_child_vertical_extent_wrap(
    child: CleanDesignTreeNode,
    widget: str,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Reserve a non-growing stack slot's full Figma height in a flow ``Column``."""
    if is_viewport_chrome_band(child):
        height = stack_flow_child_known_height(child)
        if height is None or height <= 0:
            return widget
        height_lit = format_geometry_literal(height)
        align = (
            "Alignment.bottomCenter"
            if child.stack_placement is not None and child.stack_placement.vertical == "BOTTOM"
            else "Alignment.topCenter"
        )
        return f"SizedBox(height: {height_lit}, child: Align(alignment: {align}, child: {widget}))"
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _column_is_text_primary,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_status_pill_badge,
    )

    placement = child.stack_placement
    height: float | None = None
    if placement is not None and placement.height is not None and placement.height > 0:
        height = float(placement.height)
    if height is None and child.sizing.height is not None and child.sizing.height > 0:
        height = float(child.sizing.height)
    if height is None or height <= 0:
        return widget
    height_lit = format_geometry_literal(height)
    align = "Alignment.centerLeft"
    if (
        parent_node is not None
        and parent_node.type == NodeType.STACK
        and (parent_node.alignment.cross or "").lower() in {"center", "centre"}
        and child.type in {NodeType.VECTOR, NodeType.IMAGE}
    ):
        child_width = child.sizing.width
        parent_width = parent_node.sizing.width
        if (
            child_width is not None
            and parent_width is not None
            and float(child_width) > 0
            and float(parent_width) > 0
            and float(child_width) < float(parent_width) - 1.0
        ):
            align = "Alignment.center"
    if child.type == NodeType.COLUMN and _column_is_text_primary(child):
        if all(
            item.type == NodeType.TEXT and (item.style.text_align or "LEFT").upper() == "CENTER"
            for item in child.children
        ):
            align = "Alignment.topCenter"
    if child.type == NodeType.COLUMN and any(
        grand.type == NodeType.ROW and layout_fact_row_status_pill_badge(grand)
        for grand in child.children
    ):
        align = "Alignment.center"
    if child.type == NodeType.ROW and layout_fact_row_status_pill_badge(child):
        align = "Alignment.center"
    if _stack_flow_slot_prefers_min_height(child, parent_node=parent_node):
        return (
            f"ConstrainedBox("
            f"constraints: BoxConstraints(minHeight: {height_lit}), "
            f"child: Align(alignment: {align}, child: {widget}))"
        )
    return f"SizedBox(height: {height_lit}, child: Align(alignment: {align}, child: {widget}))"


def _bound_stack_sized_box(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None = None,
) -> str | None:
    """Give ``Stack`` children of ``Column`` finite constraints (Flutter flex law)."""
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        hoist_flex_parent_data,
    )
    from figma_flutter_agent.generator.layout.widgets import _node_layout_size
    from figma_flutter_agent.generator.layout.widgets.positioned import (
        _stack_has_bottom_anchored_child,
    )
    from figma_flutter_agent.parser.interaction import (
        layout_fact_back_nav_stack,
        layout_fact_skip_control_stack,
    )

    from figma_flutter_agent.generator.layout.widgets.stepper import (
        compact_quantity_stepper_emit_width,
    )
    from figma_flutter_agent.parser.interaction import (
        layout_fact_stack_compact_quantity_stepper,
    )

    if layout_fact_stack_compact_quantity_stepper(node):
        pill_width = compact_quantity_stepper_emit_width(node)
        pill_height = node.sizing.height
        if pill_width is not None and pill_width > 0:
            width_lit = format_geometry_literal(pill_width)
            inner = widget
            trimmed = widget.lstrip()
            prefix = widget[: len(widget) - len(trimmed)]
            if trimmed.startswith("SizedBox("):
                child_marker = ", child: "
                marker_idx = trimmed.find(child_marker)
                if marker_idx > 0:
                    inner_body = trimmed[marker_idx + len(child_marker) :]
                    if inner_body.endswith(")"):
                        inner_body = inner_body[:-1]
                    inner = f"{prefix}{inner_body}"
            if pill_height is not None and float(pill_height) > 0:
                height_lit = format_geometry_literal(float(pill_height))
                return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {inner})"
            return f"SizedBox(width: {width_lit}, child: {inner})"

    placement = node.stack_placement
    width, height = _node_layout_size(node, placement)
    if width is None or width <= 0:
        return None
    if layout_fact_stack_positioned_subtitle_line(node):
        from figma_flutter_agent.generator.layout.responsive import (
            responsive_host_width_literal,
        )

        width_lit = responsive_host_width_literal(width)
        trimmed = widget.lstrip()
        if trimmed.startswith("SizedBox(") and ", height:" in trimmed.split(", child:", 1)[0]:
            return widget
        return hoist_flex_parent_data(
            lambda inner: wrap_subtitle_stack_sized_box(
                inner,
                node,
                width_lit=width_lit,
            ),
            widget,
        )
    if _stack_has_bottom_anchored_child(node):
        from figma_flutter_agent.generator.layout.responsive import (
            responsive_host_width_literal,
        )

        width_lit = responsive_host_width_literal(width)
        trimmed = widget.lstrip()
        if trimmed.startswith("Expanded("):
            return widget
        if parent_type in {NodeType.COLUMN, NodeType.CARD}:
            if is_viewport_chrome_band(node):
                if height is not None and height > 0:
                    height_lit = format_geometry_literal(height)
                    return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {widget})"
                return f"SizedBox(width: {width_lit}, child: {widget})"
            inner = widget
            if width_lit == "double.infinity" or "width:" not in widget[:120]:
                inner = f"SizedBox(width: {width_lit}, child: {widget})"
            if stack_should_flow_as_column(node):
                return f"SizedBox(width: {width_lit}, child: {inner})"
            # BottomAnchoredStackColumnBoundLaw: finite stack height must not use
            # Expanded under shrink-wrap Column hosts (unbounded main-axis chain).
            if height is not None and height > 0:
                height_lit = format_geometry_literal(height)
                return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {inner})"
            return f"SizedBox(width: {width_lit}, child: {inner})"
        if height is not None and height > 0:
            height_lit = format_geometry_literal(height)
            return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {widget})"
        return f"SizedBox(width: {width_lit}, child: {widget})"
    if height is None or height <= 0:
        if layout_fact_back_nav_stack(node) or layout_fact_skip_control_stack(node):
            side = max(float(width), 48.0)
            width = height = side
        else:
            return None
    from figma_flutter_agent.generator.layout.responsive import (
        responsive_host_width_literal,
    )

    width_lit = responsive_host_width_literal(width)
    height_lit = format_geometry_literal(height)
    if stack_should_flow_as_column(node):
        trimmed = widget.lstrip()
        if trimmed.startswith("SizedBox("):
            return widget
        return hoist_flex_parent_data(
            lambda inner: f"SizedBox(width: {width_lit}, child: {inner})",
            widget,
        )

    if layout_fact_stack_compact_quantity_stepper(node):
        return widget

    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]

    def _bound(inner: str) -> str:
        inner_trimmed = inner.lstrip()
        inner_prefix = inner[: len(inner) - len(inner_trimmed)]
        if inner_trimmed.startswith("SizedBox("):
            child_marker = ", child: "
            marker_idx = inner_trimmed.find(child_marker)
            if marker_idx < 0:
                return inner
            head = inner_trimmed[:marker_idx]
            tail = inner_trimmed[marker_idx:]
            if ", height:" in head:
                return inner
            if "width:" not in head:
                return inner
            return f"{inner_prefix}{head}, height: {height_lit}{tail}"
        return f"{inner_prefix}SizedBox(width: {width_lit}, height: {height_lit}, child: {inner})"

    return hoist_flex_parent_data(_bound, widget)


def bound_stack_scroll_list_item(
    node: CleanDesignTreeNode,
    widget: str,
) -> str | None:
    """Bind a section ``Stack`` to finite height for vertical ``ListView`` items."""
    from figma_flutter_agent.generator.layout.widgets import _node_layout_size
    from figma_flutter_agent.generator.layout.responsive import (
        responsive_host_width_literal,
    )

    placement = node.stack_placement
    width, height = _node_layout_size(node, placement)
    if width is None or float(width) <= 0:
        return None
    width_lit = responsive_host_width_literal(float(width))
    if height is None or float(height) <= 0:
        from figma_flutter_agent.generator.layout.scroll import (
            _scroll_item_root_pins_finite_main_extent,
        )

        if _scroll_item_root_pins_finite_main_extent(widget):
            return widget
        return f"SizedBox(width: {width_lit}, child: {widget})"
    height_lit = format_geometry_literal(float(height))
    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    if trimmed.startswith("SizedBox("):
        from figma_flutter_agent.generator.layout.flex_policy.wrap import (
            _extract_balanced_prefix_child,
        )

        head = trimmed.split(", child:", 1)[0]
        if ", height:" in head:
            return widget
        child_marker = ", child: "
        marker_idx = trimmed.find(child_marker)
        if marker_idx < 0:
            return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {widget})"
        inner = _extract_balanced_prefix_child(trimmed, marker_idx + len(child_marker))
        if inner is None:
            return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {widget})"
        return f"{prefix}{head}, height: {height_lit}, child: {inner})"
    return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {widget})"
