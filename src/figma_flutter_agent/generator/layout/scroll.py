"""Scrollable lists, grids, and overflow layout renderers."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import LAZY_CHILD_THRESHOLD, wrap_repaint_boundary
from figma_flutter_agent.generator.layout.responsive_grid import (
    grid_cross_axis_count_expr,
    responsive_grid_cross_axis_count,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, ScrollAxis, SizingMode


def _product_card_intrinsic_height(card: CleanDesignTreeNode) -> float | None:
    """Estimate rendered product-tile height from hero + metadata (not Figma card bbox)."""
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        layout_fact_column_product_card_footer_margin,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_has_edge_to_edge_hero_stack,
    )

    if not card_has_edge_to_edge_hero_stack(card) or len(card.children) < 2:
        return None
    hero_height = card.children[0].sizing.height
    if hero_height is None or float(hero_height) <= 0:
        return None
    meta = card.children[1]
    total = float(hero_height) + meta.padding.top + meta.padding.bottom
    for child in meta.children:
        if layout_fact_column_product_card_footer_margin(child):
            row = child.children[0]
            row_height = row.sizing.height
            total += child.padding.top + child.padding.bottom
            total += float(row_height) if row_height is not None and row_height > 0 else 44.0
        else:
            child_height = child.sizing.height
            if child_height is not None and float(child_height) > 0:
                total += float(child_height)
    return total


def _product_tile_child_aspect_ratio(node: CleanDesignTreeNode) -> float | None:
    """Return Figma card width/height for product grids (viewport-independent)."""
    ratios: list[float] = []
    for child in node.children:
        width = child.sizing.width
        height = child.sizing.height
        if height is None or float(height) <= 0:
            height = _product_card_intrinsic_height(child)
        if width is not None and height is not None and float(width) > 0 and float(height) > 0:
            ratios.append(float(width) / float(height))
    if not ratios:
        return None
    return min(ratios)


def grid_child_aspect_ratio(node: CleanDesignTreeNode) -> float | None:
    """Derive ``childAspectRatio`` for ``GridView`` children (width / height)."""
    if _grid_children_are_product_tiles(node):
        product_ratio = _product_tile_child_aspect_ratio(node)
        if product_ratio is not None:
            return product_ratio
    col_count = node.grid_column_count if node.grid_column_count is not None else 2
    cross_spacing = node.grid_column_gap if node.grid_column_gap is not None else node.spacing
    grid_height = node.sizing.height
    grid_width = node.sizing.width
    if grid_width is not None and grid_width > 0 and len(node.children) <= col_count:
        cell_width = (float(grid_width) - (col_count - 1) * float(cross_spacing)) / col_count
        if cell_width > 0:
            intrinsic_heights = [
                height
                for child in node.children
                if (height := _product_card_intrinsic_height(child)) is not None
            ]
            if intrinsic_heights:
                return cell_width / max(intrinsic_heights)
            child_heights = [
                float(child.sizing.height)
                for child in node.children
                if child.sizing.height is not None and float(child.sizing.height) > 0
            ]
            if child_heights:
                return cell_width / max(child_heights)
            if grid_height is not None and grid_height > 0:
                return cell_width / float(grid_height)
    for child in node.children:
        width = child.sizing.width
        height = child.sizing.height
        if width is None or height is None:
            continue
        if float(width) <= 0 or float(height) <= 0:
            continue
        return float(width) / float(height)
    return None


def padding_edge_insets(node: CleanDesignTreeNode) -> str | None:
    """Render EdgeInsets from Figma padding when non-zero."""
    padding = node.padding
    if padding.top == 0 and padding.bottom == 0 and padding.left == 0 and padding.right == 0:
        return None
    return (
        "const EdgeInsets.fromLTRB("
        f"{format_geometry_literal(padding.left)}, "
        f"{format_geometry_literal(padding.top)}, "
        f"{format_geometry_literal(padding.right)}, "
        f"{format_geometry_literal(padding.bottom)})"
    )


def _symmetric_pill_button_padding(node: CleanDesignTreeNode) -> str | None:
    """Horizontal Figma padding with symmetric vertical insets for pill buttons."""
    padding = node.padding
    if padding.top == 0 and padding.bottom == 0 and padding.left == 0 and padding.right == 0:
        return None
    vertical = max(padding.top, padding.bottom)
    return (
        "const EdgeInsets.fromLTRB("
        f"{format_geometry_literal(padding.left)}, "
        f"{format_geometry_literal(vertical)}, "
        f"{format_geometry_literal(padding.right)}, "
        f"{format_geometry_literal(vertical)})"
    )


def _horizontal_only_padding_edge_insets(node: CleanDesignTreeNode) -> str | None:
    """Render horizontal-only EdgeInsets when vertical padding would clip content."""
    padding = node.padding
    if padding.left == 0 and padding.right == 0:
        return None
    return (
        "const EdgeInsets.fromLTRB("
        f"{format_geometry_literal(padding.left)}, "
        "0.0, "
        f"{format_geometry_literal(padding.right)}, "
        "0.0)"
    )


def wrap_flex_auto_layout_padding(node: CleanDesignTreeNode, widget: str) -> str:
    """Wrap a flex host with Figma auto-layout padding inside the painted bounds."""
    from figma_flutter_agent.generator.layout.common import layout_fact_centered_glyph_badge
    from figma_flutter_agent.generator.layout.flex_policy import (
        button_is_pill_with_centered_label,
        layout_fact_column_tight_stack_text_host,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_segmented_tab_option_host,
        segmented_tab_option_vertical_padding_clips_label,
    )
    from figma_flutter_agent.parser.interaction import layout_fact_row_bounded_inline_control_row

    if button_is_pill_with_centered_label(node):
        height = node.sizing.height
        if (
            height is not None
            and float(height) > 0
            and len(node.children) == 1
            and node.children[0].type == NodeType.TEXT
        ):
            return widget
        inset = _symmetric_pill_button_padding(node)
        if inset is None:
            return widget
        return f"Padding(padding: {inset}, child: {widget})"
    if layout_fact_centered_glyph_badge(node) or layout_fact_column_tight_stack_text_host(node):
        return widget
    if layout_fact_row_segmented_tab_option_host(
        node
    ) and segmented_tab_option_vertical_padding_clips_label(node):
        padding = _horizontal_only_padding_edge_insets(node)
        if padding is None:
            return widget
        return f"Padding(padding: {padding}, child: {widget})"
    padding = padding_edge_insets(node)
    if padding is None:
        return widget
    if layout_fact_row_bounded_inline_control_row(node):
        return (
            f"Padding(padding: {padding}, "
            f"child: Align(alignment: Alignment.centerLeft, child: {widget}))"
        )
    return f"Padding(padding: {padding}, child: {widget})"


def scroll_axis_for_list(node: CleanDesignTreeNode) -> ScrollAxis | None:
    """Map Figma scroll axis metadata to ListView axis."""
    if node.scroll_axis == "horizontal":
        return "horizontal"
    if node.scroll_axis in {"vertical", "both"}:
        return "vertical"
    return None


def _scroll_section_child_height(child: CleanDesignTreeNode) -> float | None:
    """Return recovered finite height for a sectionized scroll child."""
    from figma_flutter_agent.generator.layout.widgets import _node_layout_size

    placement = child.stack_placement
    _, height = _node_layout_size(child, placement)
    if height is not None and float(height) > 0:
        return float(height)
    sizing_height = child.sizing.height
    if sizing_height is not None and float(sizing_height) > 0:
        return float(sizing_height)
    return None


_SCROLL_ITEM_TRANSPARENT_WRAPPERS = (
    "Align(",
    "Padding(",
    "Center(",
    "RepaintBoundary(",
    "Semantics(",
    "Opacity(",
)


def _trim_const_prefix(widget: str) -> tuple[str, str]:
    """Split leading whitespace/const from a Dart widget expression."""
    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    if trimmed.startswith("const "):
        return f"{prefix}const ", trimmed[6:].lstrip()
    return prefix, trimmed


def _scroll_item_head_before_child(trimmed: str) -> str:
    """Return the constructor argument head before the first ``child:`` marker."""
    child_marker = "child: "
    idx = trimmed.find(child_marker)
    if idx < 0:
        return trimmed[:-1] if trimmed.endswith(")") else trimmed
    return trimmed[:idx].rstrip().rstrip(",")


def _head_has_finite_height_literal(head: str) -> bool:
    """Return True when a widget constructor head pins a finite ``height``."""
    if "height:" not in head:
        return False
    return "height: double.infinity" not in head


def _scroll_item_root_pins_finite_main_extent(widget: str) -> bool:
    """Return True only when the scroll item root pins finite main-axis height.

    Nested ``Positioned`` / inner ``SizedBox`` heights must not satisfy this guard.
    """
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        _extract_balanced_prefix_child,
    )

    _, trimmed = _trim_const_prefix(widget)
    for _ in range(16):
        if trimmed.startswith("SizedBox("):
            return _head_has_finite_height_literal(_scroll_item_head_before_child(trimmed))
        if trimmed.startswith("ConstrainedBox("):
            head = _scroll_item_head_before_child(trimmed)
            return (
                "maxHeight:" in head
                and "maxHeight: double.infinity" not in head
            ) or (
                "minHeight:" in head
                and "minHeight: double.infinity" not in head
            )
        if trimmed.startswith("Container("):
            return _head_has_finite_height_literal(_scroll_item_head_before_child(trimmed))
        unwrapped = False
        for box_marker in _SCROLL_ITEM_TRANSPARENT_WRAPPERS:
            if not trimmed.startswith(box_marker):
                continue
            child_marker = "child: "
            child_start = trimmed.find(child_marker)
            if child_start < 0:
                break
            child = _extract_balanced_prefix_child(trimmed, child_start + len(child_marker))
            if child is None:
                break
            trimmed = child
            unwrapped = True
            break
        if unwrapped:
            continue
        return False
    return False


def prepare_scroll_list_item_widget(
    widget: str,
    child: CleanDesignTreeNode,
    *,
    axis: ScrollAxis,
) -> str:
    """Normalize a lazy scroll list item: strip flex leaks and bind finite extents."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        bound_stack_scroll_list_item,
    )
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        strip_flex_parent_data_deep,
    )
    from figma_flutter_agent.generator.layout.responsive import responsive_host_width_literal

    widget = strip_flex_parent_data_deep(widget)
    if axis != "vertical":
        return widget
    if _scroll_item_root_pins_finite_main_extent(widget):
        return widget
    if child.type == NodeType.STACK:
        bound = bound_stack_scroll_list_item(child, widget)
        if bound is not None:
            return bound
    height = _scroll_section_child_height(child)
    if height is None:
        return widget
    height_lit = format_geometry_literal(height)
    width_lit = responsive_host_width_literal(child.sizing.width)
    if width_lit is None:
        return f"SizedBox(height: {height_lit}, child: {widget})"
    return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {widget})"


def _scroll_list_item_widgets(
    child_widgets: list[str],
    *,
    section_children: list[CleanDesignTreeNode] | None,
    axis: ScrollAxis,
) -> list[str]:
    """Prepare lazy list item widget expressions for Flutter scroll legality."""
    if section_children is None or len(section_children) != len(child_widgets):
        from figma_flutter_agent.generator.layout.flex_policy.wrap import (
            strip_flex_parent_data_for_scroll_item,
        )

        return [strip_flex_parent_data_for_scroll_item(widget) for widget in child_widgets]
    return [
        prepare_scroll_list_item_widget(widget, child, axis=axis)
        for child, widget in zip(section_children, child_widgets, strict=True)
    ]


def index_switch_item_builder(
    child_widgets: list[str],
    *,
    section_children: list[CleanDesignTreeNode] | None = None,
    axis: ScrollAxis = "vertical",
) -> str:
    """Build itemBuilder switch body for lazy ListView/GridView."""
    scroll_items = _scroll_list_item_widgets(
        child_widgets,
        section_children=section_children,
        axis=axis,
    )
    cases = [
        f"        if (index == {index}) return {widget};"
        for index, widget in enumerate(scroll_items)
    ]
    cases.append("        return const SizedBox.shrink();")
    return "\n".join(cases)


def wrap_lazy_scrollable(
    scrollable: str,
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
) -> str:
    """Wrap scrollable widgets in Expanded when filling a parent column."""
    nested_fill = parent_type == NodeType.COLUMN and node.sizing.height_mode == SizingMode.FILL
    if nested_fill:
        return f"Expanded(child: {scrollable})"
    return scrollable


def _grid_children_are_product_tiles(node: CleanDesignTreeNode) -> bool:
    """True when every GRID child is a product card with edge-to-edge hero imagery."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_has_edge_to_edge_hero_stack,
    )

    cards = [child for child in node.children if child.type == NodeType.CARD]
    if len(cards) < 2:
        return False
    return all(card_has_edge_to_edge_hero_stack(card) for card in cards)


def _align_product_grid_children_top(child_widgets: list[str]) -> list[str]:
    """Fill each grid cell width and pin product tiles to the top."""
    return [
        "SizedBox("
        "width: double.infinity, "
        f"child: Align(alignment: Alignment.topCenter, child: {widget}))"
        for widget in child_widgets
    ]


def render_grid_view(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    parent_type: NodeType | None,
    responsive_enabled: bool = False,
    is_layout_root: bool = False,
    design_artboard_width: float | None = None,
) -> str:
    """Render a GridView for Figma GRID auto-layout frames."""
    if _grid_children_are_product_tiles(node):
        child_widgets = _align_product_grid_children_top(child_widgets)
    mobile_count = node.grid_column_count if node.grid_column_count is not None else 2
    main_spacing = node.grid_row_gap if node.grid_row_gap is not None else node.spacing
    cross_spacing = node.grid_column_gap if node.grid_column_gap is not None else node.spacing
    padding = padding_edge_insets(node)
    padding_field = f"padding: {padding}, " if padding is not None else ""
    child_count = len(child_widgets)
    use_builder = child_count >= LAZY_CHILD_THRESHOLD
    aspect_ratio = grid_child_aspect_ratio(node)
    aspect_field = (
        f"childAspectRatio: {format_micro_style_literal(aspect_ratio)}, "
        if aspect_ratio is not None
        else ""
    )

    count_prefix = ""
    count_suffix = ""
    cross_axis_field = str(mobile_count)
    if responsive_enabled and is_layout_root:
        small_count, large_count, tablet_count, desktop_count = responsive_grid_cross_axis_count(
            mobile_count,
            child_count,
        )
        if len({small_count, large_count, tablet_count, desktop_count}) > 1:
            from figma_flutter_agent.generator.layout.responsive import (
                responsive_layout_width_assignment,
            )

            width_assign = responsive_layout_width_assignment(design_artboard_width)
            count_expr = grid_cross_axis_count_expr(
                small_count,
                large_count,
                tablet_count,
                desktop_count,
            )
            count_prefix = (
                "LayoutBuilder(builder: (context, constraints) {"
                f"{width_assign} "
                f"final crossAxisCount = {count_expr}; "
                "return "
            )
            count_suffix = "; })"
            cross_axis_field = "crossAxisCount"
        else:
            cross_axis_field = str(mobile_count)

    if use_builder:
        item_builder = index_switch_item_builder(child_widgets)
        grid_view = (
            f"{count_prefix}"
            f"GridView.builder("
            f"{padding_field}"
            f"gridDelegate: SliverGridDelegateWithFixedCrossAxisCount("
            f"crossAxisCount: {cross_axis_field}, "
            f"{aspect_field}"
            f"mainAxisSpacing: {format_geometry_literal(main_spacing)}, "
            f"crossAxisSpacing: {format_geometry_literal(cross_spacing)}"
            f"), "
            f"itemCount: {child_count}, "
            f"itemBuilder: (context, index) {{\n{item_builder}\n      }}"
            f")"
            f"{count_suffix}"
        )
    else:
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        grid_view = (
            f"{count_prefix}"
            f"GridView.count("
            f"{padding_field}"
            f"crossAxisCount: {cross_axis_field}, "
            f"{aspect_field}"
            f"mainAxisSpacing: {format_geometry_literal(main_spacing)}, "
            f"crossAxisSpacing: {format_geometry_literal(cross_spacing)}, "
            f"children: [{body}]"
            f")"
            f"{count_suffix}"
        )

    nested_column = parent_type == NodeType.COLUMN and node.sizing.height_mode != SizingMode.FILL
    embedded_subtree_root = (
        not is_layout_root and parent_type is None and node.sizing.height_mode != SizingMode.FILL
    )
    nested_host = nested_column or node.nested_scroll_constraints or embedded_subtree_root
    if nested_host:
        prefix = "GridView.builder(" if use_builder else "GridView.count("
        replacement = (
            "GridView.builder(shrinkWrap: true, physics: const ClampingScrollPhysics(), "
            if use_builder
            else "GridView.count(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), "
        )
        grid_view = grid_view.replace(prefix, replacement, 1)
    return wrap_lazy_scrollable(wrap_repaint_boundary(grid_view), node, parent_type=parent_type)


def render_both_axis_scroll(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    parent_type: NodeType | None,
) -> str:
    """Render nested scroll views for Figma overflowDirection BOTH."""
    body = ", ".join(child_widgets) or "const SizedBox.shrink()"
    inner = f"Column(children: [{body}])"
    padding = padding_edge_insets(node)
    padding_field = f"padding: {padding}, " if padding is not None else ""
    scroll = (
        f"SingleChildScrollView("
        f"{padding_field}"
        f"child: SingleChildScrollView("
        f"scrollDirection: Axis.horizontal, "
        f"child: {inner}"
        f")"
        f")"
    )
    nested_fill = parent_type == NodeType.COLUMN and node.sizing.height_mode == SizingMode.FILL
    if nested_fill:
        return f"Expanded(child: {scroll})"
    return scroll


def wrap_horizontal_intrinsic_row_scroll(
    row_widget: str,
    *,
    height: float | None = None,
) -> str:
    """Wrap an intrinsic-width ``Row`` in a horizontal scroll host."""
    trimmed = row_widget.strip()
    if "mainAxisSize: MainAxisSize.min" not in trimmed:
        trimmed = trimmed.replace("Row(", "Row(mainAxisSize: MainAxisSize.min, ", 1)
    scroll = f"SingleChildScrollView(scrollDirection: Axis.horizontal, child: {trimmed})"
    if height is not None and float(height) > 0:
        height_lit = format_geometry_literal(float(height))
        return f"SizedBox(height: {height_lit}, child: {scroll})"
    return scroll


def interleave_scroll_children_with_gap(
    child_widgets: list[str],
    *,
    gap: float,
    axis: ScrollAxis,
) -> str:
    """Join scroll children with explicit ``SizedBox`` gaps (ListView has no ``spacing``)."""
    if gap <= 0 or len(child_widgets) < 2:
        return ", ".join(child_widgets) or "const SizedBox.shrink()"
    size_kw = "height" if axis == "vertical" else "width"
    gap_lit = format_geometry_literal(gap)
    parts: list[str] = []
    for index, widget in enumerate(child_widgets):
        parts.append(widget)
        if index < len(child_widgets) - 1:
            parts.append(f"SizedBox({size_kw}: {gap_lit})")
    return ", ".join(parts)


def render_scroll_list(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    axis: ScrollAxis,
    parent_type: NodeType | None,
    section_children: list[CleanDesignTreeNode] | None = None,
) -> str:
    """Render a ListView for Figma frames with overflow scrolling."""
    padding = padding_edge_insets(node)
    padding_field = f"padding: {padding}, " if padding is not None else ""
    direction_field = "scrollDirection: Axis.horizontal, " if axis == "horizontal" else ""
    child_count = len(child_widgets)
    use_builder = child_count >= LAZY_CHILD_THRESHOLD
    list_gap = float(node.spacing) if node.flex_gap_mode != "explicit" and node.spacing > 0 else 0.0

    nested_fill = (
        parent_type == NodeType.COLUMN
        and axis == "vertical"
        and node.sizing.height_mode == SizingMode.FILL
    ) or (
        parent_type == NodeType.ROW
        and axis == "horizontal"
        and node.sizing.width_mode == SizingMode.FILL
    )
    nested_column = parent_type == NodeType.COLUMN and axis == "vertical" and not nested_fill
    nested_host = nested_column or node.nested_scroll_constraints

    if use_builder:
        item_builder = index_switch_item_builder(
            child_widgets,
            section_children=section_children,
            axis=axis,
        )
        shrink_fields = (
            "shrinkWrap: true, physics: const ClampingScrollPhysics(), " if nested_host else ""
        )
        list_view = (
            f"ListView.builder("
            f"{padding_field}"
            f"{direction_field}"
            f"{shrink_fields}"
            f"itemCount: {child_count}, "
            f"itemBuilder: (context, index) {{\n{item_builder}\n      }}"
            f")"
        )
    else:
        body = interleave_scroll_children_with_gap(
            _scroll_list_item_widgets(
                child_widgets,
                section_children=section_children,
                axis=axis,
            ),
            gap=list_gap,
            axis=axis,
        )
        shrink_fields = (
            "shrinkWrap: true, physics: const ClampingScrollPhysics(), " if nested_host else ""
        )
        list_view = f"ListView({padding_field}{direction_field}{shrink_fields}children: [{body}])"

    if nested_fill:
        return f"Expanded(child: {wrap_repaint_boundary(list_view)})"
    return wrap_repaint_boundary(list_view)
