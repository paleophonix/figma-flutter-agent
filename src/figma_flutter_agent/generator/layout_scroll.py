"""Scrollable lists, grids, and overflow layout renderers."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_common import LAZY_CHILD_THRESHOLD, wrap_repaint_boundary
from figma_flutter_agent.generator.layout_responsive import (
    grid_cross_axis_count_expr,
    responsive_grid_cross_axis_count,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, ScrollAxis, SizingMode


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


def wrap_flex_auto_layout_padding(node: CleanDesignTreeNode, widget: str) -> str:
    """Wrap a flex host with Figma auto-layout padding inside the painted bounds."""
    from figma_flutter_agent.generator.layout_common import is_centered_glyph_badge

    if is_centered_glyph_badge(node):
        return widget
    padding = padding_edge_insets(node)
    if padding is None:
        return widget
    return f"Padding(padding: {padding}, child: {widget})"


def scroll_axis_for_list(node: CleanDesignTreeNode) -> ScrollAxis | None:
    """Map Figma scroll axis metadata to ListView axis."""
    if node.scroll_axis == "horizontal":
        return "horizontal"
    if node.scroll_axis in {"vertical", "both"}:
        return "vertical"
    return None


def index_switch_item_builder(child_widgets: list[str]) -> str:
    """Build itemBuilder switch body for lazy ListView/GridView."""
    cases = [
        f"        if (index == {index}) return {widget};"
        for index, widget in enumerate(child_widgets)
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
    mobile_count = node.grid_column_count if node.grid_column_count is not None else 2
    main_spacing = node.grid_row_gap if node.grid_row_gap is not None else node.spacing
    cross_spacing = node.grid_column_gap if node.grid_column_gap is not None else node.spacing
    padding = padding_edge_insets(node)
    padding_field = f"padding: {padding}, " if padding is not None else ""
    child_count = len(child_widgets)
    use_builder = child_count >= LAZY_CHILD_THRESHOLD

    count_prefix = ""
    count_suffix = ""
    cross_axis_field = str(mobile_count)
    if responsive_enabled and is_layout_root:
        small_count, large_count, tablet_count, desktop_count = responsive_grid_cross_axis_count(
            mobile_count,
            child_count,
        )
        if len({small_count, large_count, tablet_count, desktop_count}) > 1:
            from figma_flutter_agent.generator.layout_responsive import (
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
            f"mainAxisSpacing: {format_geometry_literal(main_spacing)}, "
            f"crossAxisSpacing: {format_geometry_literal(cross_spacing)}, "
            f"children: [{body}]"
            f")"
            f"{count_suffix}"
        )

    nested_column = parent_type == NodeType.COLUMN and node.sizing.height_mode != SizingMode.FILL
    nested_host = nested_column or node.nested_scroll_constraints
    if nested_host:
        prefix = "GridView.builder(" if use_builder else "GridView.count("
        replacement = (
            "GridView.builder(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), "
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


def render_scroll_list(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    axis: ScrollAxis,
    parent_type: NodeType | None,
) -> str:
    """Render a ListView for Figma frames with overflow scrolling."""
    padding = padding_edge_insets(node)
    padding_field = f"padding: {padding}, " if padding is not None else ""
    direction_field = "scrollDirection: Axis.horizontal, " if axis == "horizontal" else ""
    child_count = len(child_widgets)
    use_builder = child_count >= LAZY_CHILD_THRESHOLD

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
        item_builder = index_switch_item_builder(child_widgets)
        shrink_fields = (
            "shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), "
            if nested_host
            else ""
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
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        shrink_fields = (
            "shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), "
            if nested_host
            else ""
        )
        list_view = f"ListView({padding_field}{direction_field}{shrink_fields}children: [{body}])"

    if nested_fill:
        return f"Expanded(child: {wrap_repaint_boundary(list_view)})"
    return wrap_repaint_boundary(list_view)
