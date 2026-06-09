"""Column-specific flex policies."""

from __future__ import annotations

import re

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_TIGHT_STACK_TEXT_MAX_HEIGHT = 28.0


def column_is_oversized_photo_clip_host(node: CleanDesignTreeNode) -> bool:
    """Square clip host whose lone raster child exceeds the painted bounds."""
    if node.type != NodeType.COLUMN or len(node.children) != 1:
        return False
    child = node.children[0]
    if child.type != NodeType.IMAGE or not child.image_asset_key:
        return False
    width = node.sizing.width
    height = node.sizing.height
    child_width = child.sizing.width
    child_height = child.sizing.height
    if (
        width is None
        or height is None
        or child_width is None
        or child_height is None
        or float(width) < 64.0
        or float(height) < 64.0
    ):
        return False
    if abs(float(width) - float(height)) > max(8.0, float(width) * 0.12):
        return False
    return float(child_width) > float(width) or float(child_height) > float(height)


def _column_subtree_needs_cross_stretch(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``Column`` must stretch children to avoid clipping FILL rows."""
    from figma_flutter_agent.generator.layout.flex_policy.wrap import FlexWrapKind, resolve_flex_wrap

    if node.sizing.width_mode == SizingMode.FILL:
        return True
    if node.type == NodeType.ROW:
        for child in node.children:
            if resolve_flex_wrap(parent_type=NodeType.ROW, node=child) == FlexWrapKind.EXPANDED:
                return True
    for child in node.children:
        if _column_subtree_needs_cross_stretch(child):
            return True
    return False


def _column_is_text_primary(node: CleanDesignTreeNode) -> bool:
    """True when a COLUMN's visible content is predominantly TEXT."""
    if node.type != NodeType.COLUMN or not node.children:
        return False
    if len(node.children) == 1 and node.children[0].type == NodeType.TEXT:
        return True
    return all(child.type == NodeType.TEXT for child in node.children)


def _column_prefers_min_height_pin(node: CleanDesignTreeNode) -> bool:
    """Use ``minHeight`` (not a fixed cap) for multi-line flex column hosts under ``Row``."""
    if node.type != NodeType.COLUMN:
        return False
    if _column_is_text_primary(node):
        return True
    return len(node.children) > 1 and node.sizing.height_mode == SizingMode.FILL


def _column_spaced_stack_needs_loose_overflow(node: CleanDesignTreeNode) -> bool:
    """True when a ``Column`` stacks children with flex ``spacing``.

    Fractional Figma row slots plus ``StrutStyle`` metrics routinely exceed the
    painted bbox by sub-pixel amounts once ``spacing`` is applied.
    """
    return (
        node.type == NodeType.COLUMN
        and len(node.children) >= 2
        and (node.spacing or 0.0) > 0.0
    )


def _column_spaced_stack_sizes_intrinsically(node: CleanDesignTreeNode) -> bool:
    """True when a spaced ``Column`` must use ``MainAxisSize.min`` / skip height pins.

    Address-style title/subtitle stacks (text column + subtitle line) exceed the
    Figma bbox once ``StrutStyle`` metrics apply. Chat/list cards that pair a
    title ``Row`` with preview copy keep bounded ``minHeight`` rails.
    """
    if not _column_spaced_stack_needs_loose_overflow(node):
        return False
    return not any(child.type == NodeType.ROW for child in node.children)


def _column_spaced_stack_skip_row_height_pin(
    node: CleanDesignTreeNode,
    *,
    parent_row: CleanDesignTreeNode | None,
) -> bool:
    """True when a spaced ``Column`` under a ``Row`` must skip cross-axis height pins."""
    if parent_row is None or parent_row.type != NodeType.ROW:
        return False
    return _column_spaced_stack_sizes_intrinsically(node)


def column_is_tight_stack_text_host(node: CleanDesignTreeNode) -> bool:
    """True for metadata columns pinned inside a short absolute ``Stack`` slot."""
    if not _column_is_text_primary(node):
        return False
    if node.stack_placement is None:
        return False
    height = node.stack_placement.height
    if height is None or height <= 0:
        height = node.sizing.height
    if height is None or height <= 0:
        return False
    return float(height) <= _TIGHT_STACK_TEXT_MAX_HEIGHT


def text_host_is_tight_positioned(node: CleanDesignTreeNode) -> bool:
    """True when TEXT must not receive extra delta-top padding beyond its slot."""
    if node.type != NodeType.TEXT:
        return False
    height = node.sizing.height
    if (height is None or height <= 0) and node.stack_placement is not None:
        height = node.stack_placement.height
    if height is None or height <= 0:
        return False
    return float(height) <= _TIGHT_STACK_TEXT_MAX_HEIGHT


def column_in_bounded_positioned_host(node: CleanDesignTreeNode) -> bool:
    """True when a ``Column`` is pinned inside a fixed-height ``Stack`` slot."""
    if node.type != NodeType.COLUMN:
        return False
    height: float | None = None
    if node.stack_placement is not None:
        height = node.stack_placement.height
    if (height is None or height <= 0) and node.sizing.height is not None:
        height = node.sizing.height
    return height is not None and height > 0


def column_child_should_center_hug(
    parent: CleanDesignTreeNode,
    child: CleanDesignTreeNode,
) -> bool:
    """True when a fixed-width child should be centered in a hug/center ``Column``."""
    from figma_flutter_agent.generator.layout.flex_policy.row import row_is_status_pill_badge

    if parent.type != NodeType.COLUMN:
        return False
    child_width = child.sizing.width
    parent_width = parent.sizing.width
    if child_width is None or parent_width is None or child_width <= 0 or parent_width <= 0:
        return False
    if float(child_width) >= float(parent_width) - 1.0:
        return False
    if child.type == NodeType.ROW and row_is_status_pill_badge(child):
        return True
    return (parent.alignment.cross or "").lower() in {"center", "centre"}


def column_center_hug_child_wrap(
    parent: CleanDesignTreeNode,
    child: CleanDesignTreeNode,
    widget: str,
) -> str:
    """Center a bounded Figma frame inside a counter-axis-centered ``Column``."""
    from figma_flutter_agent.generator.layout.flex_policy.row import row_is_status_pill_badge

    if child.type == NodeType.ROW and row_is_status_pill_badge(child):
        return (
            "Align(alignment: Alignment.center, "
            f"child: IntrinsicWidth(child: {widget}))"
        )
    if _column_is_text_primary(child) or (
        child.type == NodeType.TEXT
        and (child.style.text_align or "").upper() == "CENTER"
    ):
        return (
            "Align(alignment: Alignment.topCenter, "
            f"child: SizedBox(width: double.infinity, child: {widget}))"
        )
    width = child.sizing.width
    if width is None or width <= 0:
        return widget
    from figma_flutter_agent.generator.layout.responsive import (
        responsive_host_width_literal,
    )

    width_lit = responsive_host_width_literal(
        width,
        width_mode=child.sizing.width_mode,
    )
    return (
        f"Align(alignment: Alignment.topCenter, "
        f"child: SizedBox(width: {width_lit}, child: {widget}))"
    )


def column_is_product_tile_metadata(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """Padded metadata block under a product-card hero (title block + price footer)."""
    del parent_node
    if node.type != NodeType.COLUMN or len(node.children) < 2:
        return False
    main = (node.alignment.main or "").replace("_", "").lower()
    if main != "spacebetween":
        return False
    width = node.sizing.width
    if width is None or not (120.0 <= float(width) <= 200.0):
        return False
    from figma_flutter_agent.parser.interaction import _subtree_has_currency_price

    return _subtree_has_currency_price(node.children[-1])


def column_hosts_product_card_stepper(
    node: CleanDesignTreeNode,
) -> bool:
    """Column that only sizes a compact quantity stepper for product tiles."""
    from figma_flutter_agent.parser.interaction import stack_is_compact_quantity_stepper

    return any(
        stack_is_compact_quantity_stepper(child)
        or any(stack_is_compact_quantity_stepper(grand) for grand in child.children)
        for child in node.children
    )


def column_is_card_metadata_slot(node: CleanDesignTreeNode) -> bool:
    """True for narrow right-aligned card metadata ``Column`` hosts."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        column_is_nav_tab_label_host,
    )

    if node.type != NodeType.COLUMN:
        return False
    if column_is_nav_tab_label_host(node):
        return False
    width = node.sizing.width
    if width is None or width <= 0 or width > 120.0:
        return False
    cross = (node.alignment.cross or "").lower()
    if cross in {"end", "stretch"}:
        return True
    return any(
        item.type == NodeType.TEXT and (item.style.text_align or "").upper() == "RIGHT"
        for item in node.children
    )


def column_bounded_slot_should_grow(node: CleanDesignTreeNode) -> bool:
    """True when a bounded stack slot should grow with its ``Column`` children."""
    from figma_flutter_agent.generator.layout.flex_policy.text import _text_has_multiple_lines

    if node.type == NodeType.COLUMN and node.scroll_axis == "none":
        if any(
            child.type == NodeType.TEXT and _text_has_multiple_lines(child)
            for child in node.children
        ):
            return True
        if column_in_bounded_positioned_host(node) and len(node.children) >= 2:
            return True
    if node.type == NodeType.TEXT and _text_has_multiple_lines(node):
        return True
    return False


def column_bounded_slot_needs_vertical_scroll(node: CleanDesignTreeNode) -> bool:
    """Bounded list panels grow with the page scroll — never nest scroll views."""
    return False


def column_cross_to_align_expr(cross: str | None) -> str:
    """Map Figma column cross-axis to a single-child ``Align`` expression."""
    mapping = {
        "end": "Alignment.centerRight",
        "center": "Alignment.center",
        "stretch": "Alignment.centerRight",
        "start": "Alignment.centerLeft",
    }
    return mapping.get(cross or "start", "Alignment.centerLeft")


def _column_needs_expanded_under_row(node: CleanDesignTreeNode) -> bool:
    """True when a ``Column`` in a ``Row`` needs a bounded width (``Expanded`` on main axis)."""
    from figma_flutter_agent.parser.interaction import hosts_compact_checkbox_control
    from figma_flutter_agent.generator.layout.flex_policy.wrap import FlexWrapKind, resolve_flex_wrap

    if node.type != NodeType.COLUMN:
        return False
    if hosts_compact_checkbox_control(node):
        return False
    if node.sizing.width_mode == SizingMode.FILL:
        return True
    if node.alignment.cross == "stretch":
        return True
    for child in node.children:
        if (
            resolve_flex_wrap(parent_type=NodeType.COLUMN, node=child)
            == FlexWrapKind.SIZED_BOX_WIDTH
        ):
            return True
    return False


def _resolve_column_cross_axis(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
    default: str,
) -> str:
    """``Column`` cross-axis (horizontal) stretch requires a bounded max width from the parent."""
    width = node.sizing.width
    has_pixel_width = width is not None and width > 0
    if parent_type == NodeType.ROW:
        if (
            node.sizing.width_mode == SizingMode.FILL
            or _column_needs_expanded_under_row(node)
        ):
            if default == "CrossAxisAlignment.start":
                return "CrossAxisAlignment.stretch"
            return default
        return "CrossAxisAlignment.start"
    if parent_type == NodeType.COLUMN:
        if node.sizing.width_mode == SizingMode.FILL:
            return default
        if has_pixel_width:
            return default
        return "CrossAxisAlignment.start"
    return default


def _is_form_field_group_column(node: CleanDesignTreeNode) -> bool:
    """Return True for label + field stacks that must grow past a Figma bbox height."""
    if node.type != NodeType.COLUMN:
        return False
    child_types = {child.type for child in node.children}
    if NodeType.TEXT in child_types and NodeType.INPUT in child_types:
        return True
    if NodeType.TEXT in child_types and len(node.children) > 1:
        return any(
            child.type
            in {NodeType.INPUT, NodeType.BUTTON, NodeType.COLUMN, NodeType.ROW}
            for child in node.children
        )
    return False


def _column_uses_loose_row_cross_axis_pin(
    node: CleanDesignTreeNode,
    *,
    parent_row: CleanDesignTreeNode | None = None,
) -> bool:
    """True when a compact ``Column`` under a bounded ``Row`` may use loose overflow.

  ``OverflowBox`` is only valid when the parent ``Row`` declares ``height_mode: FILL``
  (card chrome inside a fixed-height slot). ``HUG`` rows inside scroll hosts must let
  the column size intrinsically — otherwise ``Expanded`` + ``OverflowBox`` claims
  infinite height and crashes layout.
    """
    from figma_flutter_agent.generator.layout.flex_policy.text import _text_has_multiple_lines

    if node.type != NodeType.COLUMN:
        return False
    if parent_row is None or parent_row.type != NodeType.ROW:
        return False
    if parent_row.sizing.height_mode != SizingMode.FILL:
        return False
    if len(node.children) > 1:
        return True
    if _column_is_text_primary(node):
        return any(_text_has_multiple_lines(child) for child in node.children)
    return False


def wrap_column_child_width_fill(widget: str, node: CleanDesignTreeNode) -> str:
    """Wrap a COLUMN width-FILL child without leaving a ``Row`` height unbounded."""
    from figma_flutter_agent.generator.layout.responsive import responsive_host_width_literal
    from figma_flutter_agent.generator.layout.flex_policy.wrap import relax_row_cross_stretch_when_unbounded
    from figma_flutter_agent.generator.layout.flex_policy.row import row_is_icon_stepper_control_row
    from figma_flutter_agent.generator.layout.flex_policy.alignment import _flex_child_should_bind_fixed_height

    if node.type == NodeType.ROW and row_is_icon_stepper_control_row(node):
        height = node.sizing.height
        if height is not None and height > 0:
            return (
                f"SizedBox(width: double.infinity, "
                f"height: {format_geometry_literal(height)}, "
                f"child: {widget})"
            )
        return f"SizedBox(width: double.infinity, child: {widget})"

    width = node.sizing.width
    height = node.sizing.height
    width_lit = responsive_host_width_literal(
        width,
        width_mode=node.sizing.width_mode,
    )
    if node.type == NodeType.TEXT and (node.style.text_align or "").upper() == "CENTER":
        relaxed = relax_row_cross_stretch_when_unbounded(widget, node_type=node.type)
        return (
            f"SizedBox(width: {width_lit}, "
            f"child: Center(child: {relaxed}))"
        )
    from figma_flutter_agent.generator.layout.widgets.layout import (
        _stack_has_bottom_anchored_child,
    )

    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_is_positioned_subtitle_line,
        wrap_subtitle_stack_sized_box,
    )

    if node.type == NodeType.STACK and stack_is_positioned_subtitle_line(node):
        return wrap_subtitle_stack_sized_box(widget, node, width_lit=width_lit)
    if node.type == NodeType.STACK and _stack_has_bottom_anchored_child(node):
        return f"SizedBox(width: {width_lit}, child: {widget})"
    if height is not None and height > 0 and _flex_child_should_bind_fixed_height(node):
        return (
            f"SizedBox(width: {width_lit}, "
            f"height: {format_geometry_literal(height)}, "
            f"child: {widget})"
        )
    relaxed = relax_row_cross_stretch_when_unbounded(widget, node_type=node.type)
    return f"SizedBox(width: {width_lit}, child: {relaxed})"


def _coerce_column_cross_stretch_for_row_expand(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> str:
    """Stretch FILL-width ``Column`` children when wrapped in ``Expanded`` under ``Row``."""
    if parent_type != NodeType.ROW or node.type != NodeType.COLUMN:
        return widget
    if node.sizing.width_mode != SizingMode.FILL and not _column_needs_expanded_under_row(
        node
    ):
        return widget
    column_idx = _flex_column_open_index(widget)
    if column_idx is None:
        return widget
    if "crossAxisAlignment: CrossAxisAlignment.stretch" in widget[column_idx:]:
        return widget
    prefix, column_expr = widget[:column_idx], widget[column_idx:]
    patched = re.sub(
        r"crossAxisAlignment:\s*CrossAxisAlignment\.\w+",
        "crossAxisAlignment: CrossAxisAlignment.stretch",
        column_expr,
        count=1,
    )
    return prefix + patched


def _flex_column_open_index(widget: str) -> int | None:
    """Return the index of the outermost ``Column(`` in a flex child expression."""
    import re as _re

    match = _re.search(r"\bColumn\(", widget)
    return match.start() if match else None
