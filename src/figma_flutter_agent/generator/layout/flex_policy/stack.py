"""Stack-specific flex policies."""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal, round_geometry
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_STACK_PANEL_MIN_HEIGHT = 60.0
_CARD_METADATA_STACK_MAX_WIDTH = 120.0
_CARD_METADATA_STACK_MIN_HEIGHT = 40.0
_CARD_METADATA_STACK_MAX_HEIGHT = 64.0
_CARD_HERO_MIN_WIDTH = 120.0
_CARD_HERO_MIN_HEIGHT = 80.0
_CARD_HERO_MIN_HEIGHT_RATIO = 0.45
_SUBTITLE_STACK_STRUT_BUFFER = 2.0


def stack_is_positioned_subtitle_line(node: CleanDesignTreeNode) -> bool:
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
    if line_height is None or line_height > 24.0:
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
    bottom_inset = (
        float(placement.bottom) if placement and placement.bottom is not None else 0.0
    )
    extent = line_height + top_inset + bottom_inset + _SUBTITLE_STACK_STRUT_BUFFER
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
    from figma_flutter_agent.generator.layout.flex_policy.column import column_bounded_slot_should_grow

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
    return height is not None and float(height) >= _STACK_PANEL_MIN_HEIGHT


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
        or float(hero_width) < _CARD_HERO_MIN_WIDTH
        or float(hero_height) < _CARD_HERO_MIN_HEIGHT
    ):
        return False
    return float(hero_height) / float(card_height) >= _CARD_HERO_MIN_HEIGHT_RATIO


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


def stack_should_emit_as_metadata_column(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """True when a narrow card stack should flow as ``Column`` instead of ``Stack``."""
    from figma_flutter_agent.schemas import WrapKind

    if not stack_is_card_metadata_host(node, parent_node=parent_node):
        return False
    slot = node.layout_slot
    if slot is not None and WrapKind.CONSTRAINED_BOX in slot.wraps:
        return any(child.stack_placement is not None for child in node.children)
    return True


def stack_is_card_metadata_host(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """True for narrow card stacks that host timestamps and optional badges."""
    from figma_flutter_agent.generator.layout.flex_policy.row import row_is_card_composite_body

    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    if width is None or width <= 0 or width > _CARD_METADATA_STACK_MAX_WIDTH:
        return False
    height = node.sizing.height
    if height is not None and height > 0:
        if (
            _CARD_METADATA_STACK_MIN_HEIGHT
            <= float(height)
            <= _CARD_METADATA_STACK_MAX_HEIGHT
        ):
            return True
    if parent_node is not None and row_is_card_composite_body(parent_node):
        return True
    return False


def stack_metadata_timestamp_host(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """True when a stack child is the timestamp row above a notification badge."""
    if parent_node is None or parent_node.type != NodeType.STACK:
        return False
    width = parent_node.sizing.width
    if width is None or width <= 0 or width > _CARD_METADATA_STACK_MAX_WIDTH:
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
    if frame.placement_origin is not None:
        return float(frame.placement_origin.y)
    return float(frame.layout_rect.y)


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
    top = stack_child_ordinal_top(child)
    height: float | None = None
    if child.stack_placement is not None and child.stack_placement.height is not None:
        height = float(child.stack_placement.height)
    if (height is None or height <= 0) and child.sizing.height is not None and child.sizing.height > 0:
        height = float(child.sizing.height)
    return top + float(height or 0.0)


def tree_children_are_vertically_sequential(
    children: list[CleanDesignTreeNode],
) -> bool:
    """True when siblings do not overlap on the vertical axis."""
    if len(children) < 2:
        return False
    ordered = sorted(
        children,
        key=lambda child: (stack_child_ordinal_top(child), child.id),
    )
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if stack_child_ordinal_top(current) < stack_child_ordinal_bottom(previous) - 0.5:
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


def stack_should_flow_as_column(stack: CleanDesignTreeNode) -> bool:
    """True when vertically stacked panels should grow in a ``Column`` instead of ``Stack``."""
    if stack.type != NodeType.STACK or len(stack.children) < 2:
        return False
    if not stack_children_are_vertically_sequential(stack):
        return False
    growable_panels = sum(
        1 for child in stack.children if stack_child_is_growable_panel(child)
    )
    if growable_panels >= 2:
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
    return button_is_pill_with_centered_label(child) or button_should_fitted_box_label(
        child
    )


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
        column_bounded_slot_should_grow,
        _column_is_text_primary,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import row_is_status_pill_badge
    from figma_flutter_agent.parser.interaction import button_should_flow_as_column

    if parent_node is not None and parent_node.type == NodeType.BUTTON:
        if button_should_flow_as_column(parent_node):
            return True
    if child.type == NodeType.BUTTON and button_should_flow_as_column(child):
        return True
    if column_bounded_slot_should_grow(child):
        return True
    if child.type == NodeType.ROW and row_is_status_pill_badge(child):
        return True
    if child.type == NodeType.COLUMN:
        if any(
            grand.type == NodeType.ROW and row_is_status_pill_badge(grand)
            for grand in child.children
        ):
            return True
        if _column_is_text_primary(child):
            return True
    return False


def stack_flow_child_horizontal_wrap(
    child: CleanDesignTreeNode,
    widget: str,
) -> str:
    """Stretch flow-column children that were horizontally pinned in Figma."""
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
    from figma_flutter_agent.generator.layout.flex_policy.column import _column_is_text_primary
    from figma_flutter_agent.generator.layout.flex_policy.row import row_is_status_pill_badge

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
    if child.type == NodeType.COLUMN and _column_is_text_primary(child):
        if all(
            item.type == NodeType.TEXT
            and (item.style.text_align or "LEFT").upper() == "CENTER"
            for item in child.children
        ):
            align = "Alignment.topCenter"
    if child.type == NodeType.COLUMN and any(
        grand.type == NodeType.ROW and row_is_status_pill_badge(grand)
        for grand in child.children
    ):
        align = "Alignment.center"
    if child.type == NodeType.ROW and row_is_status_pill_badge(child):
        align = "Alignment.center"
    if _stack_flow_slot_prefers_min_height(child, parent_node=parent_node):
        return (
            f"ConstrainedBox("
            f"constraints: BoxConstraints(minHeight: {height_lit}), "
            f"child: Align(alignment: {align}, child: {widget}))"
        )
    return (
        f"SizedBox(height: {height_lit}, "
        f"child: Align(alignment: {align}, child: {widget}))"
    )


def _bound_stack_sized_box(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None = None,
) -> str | None:
    """Give ``Stack`` children of ``Column`` finite constraints (Flutter flex law)."""
    from figma_flutter_agent.generator.layout.widgets import _node_layout_size
    from figma_flutter_agent.generator.layout.widgets.positioned import (
        _stack_has_bottom_anchored_child,
    )
    from figma_flutter_agent.parser.interaction import (
        looks_like_back_nav_stack,
        looks_like_skip_control_stack,
    )
    from figma_flutter_agent.generator.layout.flex_policy.wrap import hoist_flex_parent_data

    placement = node.stack_placement
    width, height = _node_layout_size(node, placement)
    if width is None or width <= 0:
        return None
    if stack_is_positioned_subtitle_line(node):
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
            inner = widget
            if width_lit == "double.infinity":
                inner = f"SizedBox(width: {width_lit}, child: {widget})"
            elif "width:" not in widget[:120]:
                inner = f"SizedBox(width: {width_lit}, child: {widget})"
            return f"Expanded(child: {inner})"
        if height is not None and height > 0:
            height_lit = format_geometry_literal(height)
            return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {widget})"
        return f"SizedBox(width: {width_lit}, child: {widget})"
    if height is None or height <= 0:
        if looks_like_back_nav_stack(node) or looks_like_skip_control_stack(node):
            side = max(float(width), 48.0)
            width = height = side
        else:
            return None
    from figma_flutter_agent.generator.layout.responsive import responsive_host_width_literal

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
        return (
            f"{inner_prefix}SizedBox("
            f"width: {width_lit}, "
            f"height: {height_lit}, "
            f"child: {inner})"
        )

    return hoist_flex_parent_data(_bound, widget)
