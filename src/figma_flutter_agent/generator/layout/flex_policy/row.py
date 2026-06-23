"""Row-specific flex policies and predicates."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.geometry_facts import (
    COMPACT_CHIP_HOST_MAX_WIDTH,
    MIN_CHIP_HORIZONTAL_PADDING,
    SQUARE_ICON_CONTROL_MAX,
    SQUARE_ICON_CONTROL_MIN,
    STATUS_PILL_MAX_HEIGHT,
    TIGHT_PILL_MAX_HEIGHT,
    bounded_width_at_most,
    height_within_band,
    node_horizontal_padding_at_least,
    square_bounds_within_band,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_TIGHT_CHIP_ROW_MAX_USABLE_SPAN = 80.0
_INTRINSIC_ROW_CHILD_MAX_SPAN = 120.0
_CARD_METADATA_STACK_MAX_WIDTH = 120.0


def _row_hosts_horizontal_flex_children(node: CleanDesignTreeNode) -> bool:
    """True when a nested ``Row`` will emit ``Expanded`` / ``Flexible`` on its main axis."""
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        FlexWrapKind,
        resolve_flex_wrap,
    )

    if node.type != NodeType.ROW:
        return False
    for child in node.children:
        child_wrap = resolve_flex_wrap(parent_type=NodeType.ROW, node=child)
        if child_wrap in {FlexWrapKind.EXPANDED, FlexWrapKind.FLEXIBLE_LOOSE}:
            return True
        if child.type == NodeType.ROW and _row_hosts_horizontal_flex_children(child):
            return True
    return False


def layout_fact_row_tight_horizontal_chip(parent: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` hosts pill/badge copy in a bounded horizontal span."""
    if parent.type != NodeType.ROW:
        return False
    span = _row_usable_main_span(parent)
    if span is None:
        return False
    return span <= _TIGHT_CHIP_ROW_MAX_USABLE_SPAN


def row_hosts_equal_metric_cards(row: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` hosts equally-sized painted metric cards."""
    if row.type != NodeType.ROW or len(row.children) < 2:
        return False
    cards = [
        child
        for child in row.children
        if (
            child.type == NodeType.COLUMN
            and child.style.background_color
            and child.sizing.width_mode == SizingMode.FILL
        )
    ]
    if len(cards) < 2:
        return False
    widths = [float(child.sizing.width) for child in cards if child.sizing.width]
    if len(widths) < len(cards):
        return False
    return max(widths) - min(widths) <= 2.0


def row_equal_metric_cards_cross_axis(
    row: CleanDesignTreeNode,
    *,
    cross_axis: str,
) -> str:
    """Return a scroll-safe cross axis for equal-width stat-card rows."""
    if not row_hosts_equal_metric_cards(row):
        return cross_axis
    return "CrossAxisAlignment.center"


def wrap_equal_metric_cards_row_height(
    row: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
) -> str:
    """Pin stat-card row height when hosted under a vertically unbounded ``Column``."""
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    if not row_hosts_equal_metric_cards(row) or parent_type != NodeType.COLUMN:
        return widget
    height = row.sizing.height
    if height is None or float(height) <= 0:
        return widget
    height_lit = format_geometry_literal(float(height))
    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    if trimmed.startswith("SizedBox("):
        head = trimmed.split(", child:", 1)[0]
        if f"height: {height_lit}" in head:
            return widget
    return f"{prefix}SizedBox(height: {height_lit}, child: {trimmed})"


def layout_fact_row_numeric_counter_badge(node: CleanDesignTreeNode) -> bool:
    """Return True for compact circular numeric badges (unread counts)."""
    if node.type != NodeType.ROW or len(node.children) != 1:
        return False
    child = node.children[0]
    if child.type != NodeType.TEXT:
        return False
    text = (child.text or "").strip()
    if not text or not text.isdigit() or len(text) > 3:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return False
    if float(width) > 48.0 or float(height) > 36.0:
        return False
    return abs(float(width) - float(height)) <= max(4.0, float(width) * 0.2)


def _row_child_hosts_summary_text_leaf(child: CleanDesignTreeNode) -> bool:
    """Return True when ``child`` is or single-wraps a non-empty ``TEXT`` leaf."""
    if child.type == NodeType.TEXT and (child.text or "").strip():
        return True
    if len(child.children) == 1:
        return _row_child_hosts_summary_text_leaf(child.children[0])
    return False


def row_child_summary_text_leaf(child: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Resolve a summary-row ``TEXT`` leaf through single-child layout wrappers."""
    if child.type == NodeType.TEXT and (child.text or "").strip():
        return child
    if len(child.children) == 1:
        return row_child_summary_text_leaf(child.children[0])
    return None



def layout_fact_row_label_value_summary_row(node: CleanDesignTreeNode) -> bool:
    """Checkout-style label/value rows without a painted row background."""
    if node.type != NodeType.ROW or len(node.children) != 2:
        return False
    main = (node.alignment.main or "").replace("_", "").lower()
    if main != "spacebetween":
        return False
    return _row_child_hosts_summary_text_leaf(
        node.children[0]
    ) and _row_child_hosts_summary_text_leaf(node.children[1])


def layout_fact_row_space_between_text_metric_row(node: CleanDesignTreeNode) -> bool:
    """Painted or plain summary row with label/value text at opposite ends."""
    if layout_fact_row_label_value_summary_row(node):
        return True
    if node.type != NodeType.ROW or len(node.children) != 2:
        return False
    main = (node.alignment.main or "").replace("_", "").lower()
    if main != "spacebetween":
        return False
    if not node.style.background_color:
        return False

    def _text_leaf(child: CleanDesignTreeNode) -> bool:
        if child.type == NodeType.TEXT and (child.text or "").strip():
            return True
        if child.type == NodeType.STACK and len(child.children) == 1:
            return child.children[0].type == NodeType.TEXT and bool(
                (child.children[0].text or "").strip()
            )
        return False

    return _text_leaf(node.children[0]) and _text_leaf(node.children[1])


def layout_fact_row_product_card_price_footer_row(node: CleanDesignTreeNode) -> bool:
    """Price column paired with a compact quantity stepper inside a product tile."""
    from figma_flutter_agent.parser.interaction import (
        layout_fact_row_product_card_price_footer_row as _row_is_product_card_price_footer_row,
    )

    return _row_is_product_card_price_footer_row(node)


def layout_fact_row_icon_stepper_control_row(node: CleanDesignTreeNode) -> bool:
    """Return True for minus/value/plus rows with tappable buttons at both ends."""
    if node.type != NodeType.ROW or len(node.children) < 3:
        return False
    first_child = node.children[0]
    last_child = node.children[-1]
    if first_child.type != NodeType.BUTTON or last_child.type != NodeType.BUTTON:
        return False
    return any(child.sizing.width_mode == SizingMode.FILL for child in node.children[1:-1])


def layout_fact_row_status_pill_badge(node: CleanDesignTreeNode) -> bool:
    """Return True when a painted flex pill should hug and center its label."""
    if layout_fact_row_numeric_counter_badge(node):
        return False
    if node.type not in {NodeType.ROW, NodeType.COLUMN}:
        return False
    height = node.sizing.height
    if not height_within_band(height, max_height=STATUS_PILL_MAX_HEIGHT):
        return False
    if not node.style.background_color:
        return False
    if not node.children:
        return False
    if len(node.children) == 1 and node.children[0].type == NodeType.TEXT:
        return True
    return all(child.type == NodeType.TEXT for child in node.children)


def layout_fact_row_tight_overflow_guard_label_row(node: CleanDesignTreeNode) -> bool:
    """Unpainted bounded row whose sole label must clip, not FittedBox-scale."""
    from figma_flutter_agent.generator.layout.common import layout_fact_centered_glyph_badge

    if layout_fact_row_tight_horizontal_pill_label(node):
        return False
    if layout_fact_row_numeric_counter_badge(node) or layout_fact_centered_glyph_badge(node):
        return False
    if node.type != NodeType.ROW or len(node.children) != 1:
        return False
    if node.children[0].type != NodeType.TEXT:
        return False
    return layout_fact_row_tight_horizontal_chip(node)


def layout_fact_row_tight_horizontal_pill_label(parent: CleanDesignTreeNode) -> bool:
    """Return True when a tight ``Row`` is a pill label host (not a square glyph badge)."""
    if layout_fact_row_numeric_counter_badge(parent):
        return False
    if layout_fact_row_label_value_summary_row(parent):
        return False
    if not layout_fact_row_tight_horizontal_chip(parent):
        return False
    height = parent.sizing.height
    if height_within_band(height, max_height=TIGHT_PILL_MAX_HEIGHT) and parent.style.background_color:
        return True
    if parent.padding is not None:
        from figma_flutter_agent.generator.layout.geometry_facts import horizontal_padding_sum

        return horizontal_padding_sum(parent.padding) > 0
    return False


def layout_fact_row_toolbar_leading_title_row(row: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` is a leading control beside a title column."""
    if row.type != NodeType.ROW or len(row.children) != 2:
        return False
    lead, trail = row.children
    if lead.type != NodeType.BUTTON:
        return False
    width = lead.sizing.width
    height = lead.sizing.height
    if not square_bounds_within_band(
        width,
        height,
        min_edge=SQUARE_ICON_CONTROL_MIN,
        max_edge=SQUARE_ICON_CONTROL_MAX,
    ):
        return False
    if trail.type != NodeType.COLUMN:
        return False
    return any(grandchild.type == NodeType.TEXT for grandchild in trail.children)


def row_hosts_chip_beside_heading(row: CleanDesignTreeNode) -> bool:
    """True when a ``Row`` pairs a heading column with a fixed-width status chip."""
    if row.type != NodeType.ROW:
        return False
    has_chip = any(_row_child_looks_like_chip_host(child) for child in row.children)
    if not has_chip:
        return False
    return any(
        child.type == NodeType.COLUMN
        and any(grandchild.type == NodeType.TEXT for grandchild in child.children)
        for child in row.children
    )


def _row_child_looks_like_chip_host(child: CleanDesignTreeNode) -> bool:
    """True when a bounded padded row/frame hosts badge/chip copy."""
    if child.type not in {NodeType.ROW, NodeType.CONTAINER}:
        return False
    if not bounded_width_at_most(child.sizing, COMPACT_CHIP_HOST_MAX_WIDTH):
        return False
    return node_horizontal_padding_at_least(child, MIN_CHIP_HORIZONTAL_PADDING)


def _row_child_is_painted_status_chip(child: CleanDesignTreeNode) -> bool:
    """True when a row child is a painted status/stepper chip pill."""
    if layout_fact_row_status_pill_badge(child):
        return True
    if layout_fact_row_tight_horizontal_pill_label(child):
        return True
    if child.type != NodeType.ROW or not child.style.background_color:
        return False
    return row_child_summary_text_leaf(child) is not None


def row_exceeds_parent_content_width(
    row: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """True when a fixed-width row is wider than its bounded column parent."""
    row_width = row.sizing.width
    if row_width is None or float(row_width) <= 0 or parent_node is None:
        return False
    parent_width = parent_node.sizing.width
    if parent_width is None or float(parent_width) <= 0:
        return False
    return float(row_width) > float(parent_width) + 0.5


def layout_fact_row_overflowing_painted_chip_strip(
    row: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """True when a painted chip strip row exceeds its parent content band."""
    from figma_flutter_agent.parser.interaction.chip_variant import is_tag_component_chip_row

    if row.type != NodeType.ROW or len(row.children) < 2:
        return False
    if is_tag_component_chip_row(row):
        return False
    if not all(_row_child_is_painted_status_chip(child) for child in row.children):
        return False
    return row_exceeds_parent_content_width(row, parent_node)


def _row_usable_main_span(parent: CleanDesignTreeNode) -> float | None:
    """Return the ROW main-axis span after horizontal padding."""
    if parent.type != NodeType.ROW:
        return None
    span = parent.sizing.width
    if (span is None or span <= 0) and parent.geometry_frame is not None:
        span = parent.geometry_frame.intrinsic_size.width
    if span is None or span <= 0:
        return None
    if parent.padding is not None:
        span -= float(parent.padding.left or 0.0) + float(parent.padding.right or 0.0)
    return max(0.0, float(span))


def _child_main_span(child: CleanDesignTreeNode) -> float | None:
    """Return a child's planned main-axis span for ROW flex allocation."""
    span = child.sizing.width
    if (span is None or span <= 0) and child.geometry_frame is not None:
        span = child.geometry_frame.intrinsic_size.width
    if span is None or span <= 0:
        return None
    return float(span)


def _row_child_keeps_intrinsic_width(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """True when a bounded ROW child should not receive ``Flexible``/``Expanded``."""
    if parent_node is None or parent_node.type != NodeType.ROW:
        return False
    if node.sizing.width_mode not in {SizingMode.FIXED, SizingMode.HUG}:
        return False
    span = _child_main_span(node)
    if span is None or span <= 0 or span > _INTRINSIC_ROW_CHILD_MAX_SPAN:
        return False
    if node.type in {
        NodeType.BUTTON,
        NodeType.CONTAINER,
        NodeType.IMAGE,
        NodeType.VECTOR,
        NodeType.INPUT,
        NodeType.CARD,
    }:
        return True
    if node.type == NodeType.ROW:
        return True
    return False


def _should_expand_sole_undersized_row_child(
    parent_node: CleanDesignTreeNode,
    node: CleanDesignTreeNode,
) -> bool:
    """True when a sole HUG/FIXED child should grow to fill a wider FILL ROW."""
    from figma_flutter_agent.generator.geometry.affine import geom_epsilon

    if parent_node.type != NodeType.ROW:
        return False
    if parent_node.sizing.width_mode != SizingMode.FILL:
        return False
    if len(parent_node.children) != 1 or parent_node.children[0].id != node.id:
        return False
    if node.type not in {NodeType.ROW, NodeType.COLUMN}:
        return False
    if node.sizing.width_mode not in {SizingMode.FIXED, SizingMode.HUG}:
        return False
    if node.sizing.height_mode == SizingMode.FILL:
        return False
    parent_span = _row_usable_main_span(parent_node)
    child_span = _child_main_span(node)
    if parent_span is None or child_span is None:
        return False
    return child_span < parent_span - geom_epsilon()


def _row_hosts_title_text(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` subtree carries heading/body copy beside chrome."""
    if node.type == NodeType.TEXT:
        return True
    for child in node.children:
        if _row_hosts_title_text(child):
            return True
    return False


def _row_hosts_compact_icon_with_text(node: CleanDesignTreeNode) -> bool:
    """Return True when a header ``Row`` mixes a circular icon button with title copy."""
    from figma_flutter_agent.parser.interaction import (
        layout_fact_back_nav_stack,
        layout_fact_compact_icon_action_button,
    )

    if node.type != NodeType.ROW:
        return False

    def _hosts_icon_button(item: CleanDesignTreeNode) -> bool:
        if layout_fact_compact_icon_action_button(item) or layout_fact_back_nav_stack(item):
            return True
        return any(_hosts_icon_button(child) for child in item.children)

    return _hosts_icon_button(node) and _row_hosts_title_text(node)


def _row_hosts_stacked_column_peer(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` pairs a fixed bbox with a multi-child ``Column`` peer."""
    if node.type != NodeType.ROW:
        return False
    return any(
        child.type == NodeType.COLUMN and len(child.children) >= 2 for child in node.children
    )


def _parent_row_has_bounded_height(parent_node: CleanDesignTreeNode | None) -> bool:
    """Return True when the flex parent ``Row`` pins a finite cross-axis height."""
    if parent_node is None or parent_node.type != NodeType.ROW:
        return False
    height = parent_node.sizing.height
    return height is not None and height > 0


def _column_peer_in_bounded_row(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Return True when a multi-child ``Column`` sits in a height-bounded ``Row``."""
    if node.type != NodeType.COLUMN or len(node.children) < 2:
        return False
    return _parent_row_has_bounded_height(parent_node)


def _resolve_row_cross_axis(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
    default: str,
) -> str:
    """``Row`` cross-axis (vertical) stretch requires a bounded max height from the parent.

    ``Wrap``, nested ``Row``, and ``Button`` hosts never bound cross-axis height for
    children, so stretch is relaxed to ``start``.
    """
    if layout_fact_row_product_card_price_footer_row(node):
        return "CrossAxisAlignment.center"
    height = node.sizing.height
    has_pixel_height = height is not None and height > 0
    if parent_type in {NodeType.ROW, NodeType.BUTTON, NodeType.WRAP}:
        return "CrossAxisAlignment.start"
    if layout_fact_row_card_composite_body(node):
        return "CrossAxisAlignment.center"
    if parent_type == NodeType.COLUMN:
        if node.sizing.height_mode == SizingMode.FILL:
            return default
        if has_pixel_height and _row_hosts_compact_icon_with_text(node):
            return "CrossAxisAlignment.center"
        if has_pixel_height and _row_hosts_title_text(node):
            return "CrossAxisAlignment.start"
        if has_pixel_height:
            return default
        return "CrossAxisAlignment.start"
    return default


def layout_fact_row_card_composite_body(row: CleanDesignTreeNode) -> bool:
    """True when a ``Row`` pairs a content column with a metadata rail."""
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        layout_fact_column_card_metadata_slot,
    )

    if row.type != NodeType.ROW or len(row.children) != 2:
        return False
    has_metadata = False
    has_content = False
    for child in row.children:
        child_width = float(child.sizing.width or 0.0)
        if (
            child.type == NodeType.STACK
            and child_width <= _CARD_METADATA_STACK_MAX_WIDTH
            or child.type == NodeType.COLUMN
            and layout_fact_column_card_metadata_slot(child)
            or (child.type == NodeType.TEXT and 0 < child_width <= _CARD_METADATA_STACK_MAX_WIDTH)
        ):
            has_metadata = True
        elif child.type == NodeType.COLUMN and child_width > _CARD_METADATA_STACK_MAX_WIDTH:
            has_content = True
    return has_metadata and has_content


def _row_hosts_stack_flow_column_peer(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` pairs a fixed bbox with a flow-column ``Stack`` peer."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import stack_should_flow_as_column

    if node.type != NodeType.ROW:
        return False
    return any(
        child.type == NodeType.STACK and stack_should_flow_as_column(child)
        for child in node.children
    )


def row_overflow_budget(
    row: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> float | None:
    """Return ROW main-axis budget for overflow guard (row span, else parent content)."""
    span = _row_usable_main_span(row)
    if span is not None and span > 0:
        return span
    if parent_node is None:
        return None
    parent_span = parent_node.sizing.width
    if (parent_span is None or parent_span <= 0) and parent_node.geometry_frame is not None:
        parent_span = parent_node.geometry_frame.intrinsic_size.width
    if parent_span is None or parent_span <= 0:
        return None
    if parent_node.padding is not None:
        parent_span -= float(parent_node.padding.left or 0.0) + float(
            parent_node.padding.right or 0.0
        )
    return max(0.0, float(parent_span))


def _widget_has_flex_parent_data(widget: str) -> bool:
    """Return True when ``widget`` is already wrapped in ``Expanded``/``Flexible``."""
    trimmed = widget.lstrip()
    return trimmed.startswith(("Expanded(", "Flexible(", "const Expanded(", "const Flexible("))


def _row_intrinsic_main_axis_total(row: CleanDesignTreeNode) -> float | None:
    """Sum planned child main-axis spans for gap-budget checks (pre-emit flex wrappers)."""
    total = 0.0
    for child in row.children:
        span = _child_main_span(child)
        if span is None:
            return None
        total += span
    return total


def row_rigid_main_axis_overflow(
    row: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
    tolerance: float | None = None,
) -> float:
    """Return positive overflow px when rigid ROW children exceed the usable main span.

    FILL-mode children are skipped in the rigid sum because they are emitted as
    ``Expanded`` and flex to absorb remaining space.

    When the Row's own width is not directly determinable, the parent node's
    content width is used as the overflow budget (same fallback as
    ``row_overflow_budget``).
    """
    from figma_flutter_agent.generator.geometry.affine import geom_epsilon

    if row.type != NodeType.ROW or len(row.children) < 2:
        return 0.0
    tol = geom_epsilon() if tolerance is None else tolerance
    parent_span = row_overflow_budget(row, parent_node)
    if parent_span is None or parent_span <= 0:
        return 0.0
    gap_total = float(row.spacing) * max(0, len(row.children) - 1)
    rigid_sum = 0.0
    for child in row.children:
        if child.sizing.width_mode == SizingMode.FILL:
            continue
        span = _child_main_span(child)
        if span is None or span <= 0:
            continue
        rigid_sum += span
    overflow = rigid_sum + gap_total - parent_span
    return overflow if overflow > tol else 0.0


def apply_row_rigid_overflow_relief(
    row: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> list[str]:
    """Wrap rigid peers in ``Expanded`` when a bounded ROW would overflow at runtime."""
    if (
        row_rigid_main_axis_overflow(row, parent_node=parent_node) <= 0
        or len(child_widgets) != len(row.children)
    ):
        return child_widgets
    result = list(child_widgets)
    vector_indices = [
        index for index, child in enumerate(row.children) if child.type == NodeType.VECTOR
    ]
    if len(vector_indices) >= 2:
        for index in vector_indices:
            if not _widget_has_flex_parent_data(result[index]):
                result[index] = f"Expanded(child: {result[index]})"
        return result
    image_indices = [
        index for index, child in enumerate(row.children) if child.type == NodeType.IMAGE
    ]
    if len(image_indices) >= 2:
        for index in image_indices:
            if not _widget_has_flex_parent_data(result[index]):
                result[index] = f"Expanded(child: {result[index]})"
        return result
    text_indices = [
        index for index, child in enumerate(row.children) if child.type == NodeType.TEXT
    ]
    if len(text_indices) == 1 and len(row.children) > 1:
        index = text_indices[0]
        if not _widget_has_flex_parent_data(result[index]):
            result[index] = f"Expanded(child: {result[index]})"
        return result
    eligible: list[tuple[float, int]] = []
    for index, child in enumerate(row.children):
        if _widget_has_flex_parent_data(result[index]):
            continue
        if child.type in {NodeType.BUTTON, NodeType.INPUT}:
            continue
        span = _child_main_span(child)
        eligible.append((span or 0.0, index))
    if eligible:
        text_eligible = [
            (span, idx)
            for span, idx in eligible
            if row.children[idx].type == NodeType.TEXT
        ]
        pool = text_eligible if text_eligible else eligible
        pool.sort(reverse=True)
        _, best_index = pool[0]
        result[best_index] = f"Expanded(child: {result[best_index]})"
    return result


_OVERFLOW_SAFETY_TOTAL = 0.5
_TEXT_RUNTIME_MAIN_AXIS_BUFFER_PX = 2.0


def _text_runtime_main_axis_buffer(row: CleanDesignTreeNode) -> float:
    """Reserve main-axis slack for Flutter text metrics wider than Figma boxes."""
    from figma_flutter_agent.schemas import NodeType

    text_children = sum(1 for child in row.children if child.type == NodeType.TEXT)
    return float(text_children) * _TEXT_RUNTIME_MAIN_AXIS_BUFFER_PX


def resolve_row_emit_spacing_body(
    row: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    parent_node: CleanDesignTreeNode | None,
) -> tuple[str, str, bool]:
    """Return spacing field, children body, and whether the row needs ``FittedBox`` wrap."""
    from figma_flutter_agent.generator.geometry.affine import geom_epsilon
    from figma_flutter_agent.generator.layout.widgets.flex_sizing import (
        _flex_spacing_field,
        flex_children_body,
    )
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    spacing_field = _flex_spacing_field(row)
    has_explicit_gaps = row.flex_gap_mode == "explicit" and bool(row.flex_explicit_gaps)

    if len(row.children) >= 2 and (spacing_field or has_explicit_gaps):
        row_available = row_overflow_budget(row, parent_node)
        child_total = _row_intrinsic_main_axis_total(row)
        if (
            row_available is not None
            and row_available > 0
            and child_total is not None
        ):
            n_gaps = len(row.children) - 1
            gap_total = float(row.spacing) * n_gaps if spacing_field else 0.0
            if has_explicit_gaps and row.flex_explicit_gaps:
                gaps = row.flex_explicit_gaps
                gap_total = sum(
                    float(gaps[min(index, len(gaps) - 1)]) for index in range(n_gaps)
                )
            text_buffer = _text_runtime_main_axis_buffer(row)
            if child_total + gap_total > row_available + geom_epsilon() - text_buffer:
                spacing_field = ""
                available_gap = max(0.0, row_available - child_total)
                safety_per_gap = _OVERFLOW_SAFETY_TOTAL / n_gaps if n_gaps > 0 else 0.0
                scaled_gap = (
                    max(0.0, available_gap / n_gaps - safety_per_gap) if n_gaps > 0 else 0.0
                )
                gap_lit = format_geometry_literal(scaled_gap)
                parts: list[str] = []
                for index, widget in enumerate(child_widgets):
                    parts.append(widget)
                    if index < len(child_widgets) - 1:
                        parts.append(f"SizedBox(width: {gap_lit})")
                return spacing_field, ", ".join(parts), False

    relieved = apply_row_rigid_overflow_relief(
        row,
        child_widgets,
        parent_node=parent_node,
    )

    if len(row.children) < 2 or not (spacing_field or has_explicit_gaps):
        return spacing_field, flex_children_body(row, relieved, axis="horizontal"), False

    row_available = row_overflow_budget(row, parent_node)
    if row_available is None or row_available <= 0:
        return spacing_field, flex_children_body(row, relieved, axis="horizontal"), False

    child_total = _row_intrinsic_main_axis_total(row)
    if child_total is None:
        return "", flex_children_body(row, relieved, axis="horizontal"), True

    n_gaps = len(row.children) - 1
    gap_total = float(row.spacing) * n_gaps if spacing_field else 0.0
    if has_explicit_gaps and row.flex_explicit_gaps:
        gaps = row.flex_explicit_gaps
        gap_total = sum(float(gaps[min(index, len(gaps) - 1)]) for index in range(n_gaps))

    if child_total + gap_total <= row_available + geom_epsilon() - _text_runtime_main_axis_buffer(row):
        return spacing_field, flex_children_body(row, relieved, axis="horizontal"), False

    spacing_field = ""
    available_gap = max(0.0, row_available - child_total)
    safety_per_gap = _OVERFLOW_SAFETY_TOTAL / n_gaps if n_gaps > 0 else 0.0
    scaled_gap = max(0.0, available_gap / n_gaps - safety_per_gap) if n_gaps > 0 else 0.0
    gap_lit = format_geometry_literal(scaled_gap)
    parts = []
    for index, widget in enumerate(relieved):
        parts.append(widget)
        if index < len(relieved) - 1:
            parts.append(f"SizedBox(width: {gap_lit})")
    return spacing_field, ", ".join(parts), False


_SEGMENTED_TAB_HOST_MIN_HEIGHT = 28.0
_SEGMENTED_TAB_HOST_MAX_HEIGHT = 48.0


def layout_fact_row_segmented_tab_option_host(row: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` is a single tab label inside a segmented control."""
    if row.type != NodeType.ROW:
        return False
    text_children = [child for child in row.children if child.type == NodeType.TEXT]
    if len(text_children) != 1:
        return False
    if len(row.children) != 1:
        return False
    return bool((text_children[0].text or "").strip())


def layout_fact_row_segmented_tab_switcher_host(row: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` hosts two side-by-side segmented tab options."""
    if row.type != NodeType.ROW or len(row.children) != 2:
        return False
    height = row.sizing.height
    if height is None or not (
        _SEGMENTED_TAB_HOST_MIN_HEIGHT <= float(height) <= _SEGMENTED_TAB_HOST_MAX_HEIGHT
    ):
        return False
    for child in row.children:
        if not layout_fact_row_segmented_tab_option_host(child):
            return False
    return True


def segmented_tab_option_vertical_padding_clips_label(row: CleanDesignTreeNode) -> bool:
    """Return True when Figma vertical padding would clip the tab label line-box."""
    from figma_flutter_agent.generator.layout.flex_policy.extents import (
        _row_padded_interior_height,
        _row_text_cross_axis_extent,
    )

    if not layout_fact_row_segmented_tab_option_host(row):
        return False
    label = next(child for child in row.children if child.type == NodeType.TEXT)
    interior = _row_padded_interior_height(row)
    line_box = _row_text_cross_axis_extent(label)
    if interior is None or line_box is None:
        return False
    return float(interior) + 0.5 < float(line_box)
