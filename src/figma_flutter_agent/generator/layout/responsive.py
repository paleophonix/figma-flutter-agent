"""Breakpoint-driven column/grid reflow helpers (spec §7.3)."""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import NodeType

_WIDE_COLUMN_REFLOW = "AppBreakpoints.isWideLayout(width)"
_SIDE_NAV_LAYOUT = "AppBreakpoints.isDesktop(width) || AppBreakpoints.isTablet(width)"
# Match ``AppBreakpoints.mobileSmallMax``: Figma frames at or below this width are
# mobile-only designs and must not reflow when hosted in a wide web viewport.
_MOBILE_ONLY_ARTBOARD_MAX_WIDTH = 480.0


def responsive_layout_width_assignment(design_artboard_width: float | None) -> str:
    """Assign ``width`` for breakpoint checks inside ``LayoutBuilder``.

    Args:
        design_artboard_width: Root Figma frame width when known.

    Returns:
        A Dart ``final width = …;`` statement.
    """
    if (
        design_artboard_width is None
        or design_artboard_width > _MOBILE_ONLY_ARTBOARD_MAX_WIDTH
    ):
        return "final width = constraints.maxWidth;"
    cap = format_geometry_literal(design_artboard_width)
    return f"final width = constraints.maxWidth.clamp(0.0, {cap});"


def child_is_bottom_nav(widget: str) -> bool:
    """Return True when a child widget expression is the generated adaptive nav chrome."""
    return "_LayoutChromeNav(" in widget or "_LayoutBottomNav(" in widget


def should_responsive_reflow(child_widgets: list[str]) -> bool:
    """Return True when column children should reflow to Row on wide screens."""
    if len(child_widgets) < 2 or len(child_widgets) > 4:
        return False
    cluster_refs = sum(
        1
        for widget in child_widgets
        if widget.strip().startswith("const ") and "Widget()" in widget
    )
    return cluster_refs < len(child_widgets)


def should_apply_responsive_column_reflow(
    *,
    responsive_enabled: bool,
    scroll_axis: str,
    is_layout_root: bool,
    parent_type: NodeType | None,
    child_widgets: list[str],
) -> bool:
    """Return True when a Column should reflow to Row on mobile-large+ widths."""
    if not responsive_enabled or scroll_axis != "none":
        return False
    if not should_responsive_reflow(child_widgets):
        return False
    return is_layout_root


def _wrap_main_and_nav_chrome(
    *,
    main_axis: str,
    cross_axis: str,
    main_body: str,
    nav_widget: str,
    design_artboard_width: float | None = None,
) -> str:
    """Place main content and nav as bottom bar (mobile) or side rail (tablet/desktop)."""
    width_assign = responsive_layout_width_assignment(design_artboard_width)
    mobile_column = f"Column(children: [Expanded(child: {main_body}), {nav_widget}])"
    return (
        f"LayoutBuilder("
        f"builder: (context, constraints) {{"
        f"{width_assign}"
        f"if ({_SIDE_NAV_LAYOUT}) {{"
        f"return Row("
        f"crossAxisAlignment: CrossAxisAlignment.stretch, "
        f"children: ["
        f"{nav_widget}, "
        f"Expanded(child: {main_body})"
        f"]"
        f");"
        f"}}"
        f"return {mobile_column};"
        f"}})"
    )


def wrap_responsive_root_column(
    *,
    main_axis: str,
    cross_axis: str,
    child_widgets: list[str],
    design_artboard_width: float | None = None,
    spacing_field: str = "",
) -> str:
    """Reflow a Column to Row on mobile-large, tablet, and desktop (spec §7.3)."""
    width_assign = responsive_layout_width_assignment(design_artboard_width)
    nav_widget: str | None = None
    main_widgets = child_widgets
    if child_widgets and child_is_bottom_nav(child_widgets[-1]):
        nav_widget = child_widgets[-1]
        main_widgets = child_widgets[:-1]

    if nav_widget is not None:
        if should_responsive_reflow(main_widgets) and len(main_widgets) >= 2:
            row_children = ", ".join(f"Expanded(child: {widget})" for widget in main_widgets)
            main_body = (
                f"Row(crossAxisAlignment: CrossAxisAlignment.start, children: [{row_children}])"
            )
        else:
            body = ", ".join(main_widgets) or "const SizedBox.shrink()"
            main_body = (
                f"Column(mainAxisAlignment: {main_axis}, crossAxisAlignment: {cross_axis}, "
                f"{spacing_field}children: [{body}])"
            )
        return _wrap_main_and_nav_chrome(
            main_axis=main_axis,
            cross_axis=cross_axis,
            main_body=main_body,
            nav_widget=nav_widget,
            design_artboard_width=design_artboard_width,
        )

    column_body = ", ".join(child_widgets) or "const SizedBox.shrink()"
    mobile_small_column = (
        f"Column(mainAxisAlignment: {main_axis}, crossAxisAlignment: {cross_axis}, "
        f"{spacing_field}children: [{column_body}])"
    )
    if not should_responsive_reflow(child_widgets):
        return mobile_small_column

    if len(main_widgets) < 2:
        return mobile_small_column

    row_children = ", ".join(f"Expanded(child: {widget})" for widget in main_widgets)
    wide_row = f"Row(crossAxisAlignment: CrossAxisAlignment.start, children: [{row_children}])"
    return (
        f"LayoutBuilder("
        f"builder: (context, constraints) {{"
        f"{width_assign}"
        f"if ({_WIDE_COLUMN_REFLOW}) {{"
        f"return {wide_row};"
        f"}}"
        f"return {mobile_small_column};"
        f"}})"
    )


def responsive_grid_cross_axis_count(
    base_count: int,
    child_count: int,
) -> tuple[int, int, int, int]:
    """Derive crossAxisCount for mobile-small, mobile-large, tablet, and desktop.

    Args:
        base_count: Column count from the Figma GRID frame (mobile-large baseline).
        child_count: Number of grid children.

    Returns:
        Tuple of (mobile_small, mobile_large, tablet, desktop) column counts.
    """
    large = max(1, base_count)
    small = 1 if large >= 2 else large
    tablet = min(large + 1, max(child_count, 1))
    desktop = min(large + 2, max(child_count, 1))
    return small, large, tablet, desktop


def grid_cross_axis_count_expr(
    mobile_small_count: int,
    mobile_large_count: int,
    tablet_count: int,
    desktop_count: int,
) -> str:
    """Build a Dart expression for breakpoint-aware grid column count."""
    counts = (mobile_small_count, mobile_large_count, tablet_count, desktop_count)
    if len(set(counts)) == 1:
        return str(mobile_small_count)
    return (
        f"AppBreakpoints.isDesktop(width) ? {desktop_count} : "
        f"(AppBreakpoints.isTablet(width) ? {tablet_count} : "
        f"(AppBreakpoints.isMobileLarge(width) ? {mobile_large_count} : {mobile_small_count}))"
    )
