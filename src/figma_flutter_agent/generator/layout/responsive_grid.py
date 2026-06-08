"""Responsive grid column-count helpers."""

from __future__ import annotations


def responsive_grid_cross_axis_count(
    base_count: int,
    child_count: int,
) -> tuple[int, int, int, int]:
    """Derive crossAxisCount for mobile-small, mobile-large, tablet, and desktop."""
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
