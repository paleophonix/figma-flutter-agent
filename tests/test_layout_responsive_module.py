"""Unit tests for layout_responsive helpers."""

from figma_flutter_agent.generator.layout_responsive import (
    grid_cross_axis_count_expr,
    responsive_grid_cross_axis_count,
    should_apply_responsive_column_reflow,
    should_responsive_reflow,
    wrap_responsive_root_column,
)
from figma_flutter_agent.schemas import NodeType


def test_should_responsive_reflow_rejects_single_child() -> None:
    assert should_responsive_reflow(["const A()"]) is False


def test_should_apply_responsive_column_reflow_for_nested_column() -> None:
    assert should_apply_responsive_column_reflow(
        responsive_enabled=True,
        scroll_axis="none",
        is_layout_root=False,
        parent_type=NodeType.COLUMN,
        child_widgets=["Text('A')", "Text('B')"],
    )


def test_wrap_responsive_root_column_emits_layout_builder() -> None:
    widget = wrap_responsive_root_column(
        main_axis="MainAxisAlignment.start",
        cross_axis="CrossAxisAlignment.stretch",
        child_widgets=["Text('A')", "Text('B')"],
    )

    assert "LayoutBuilder(" in widget
    assert "AppBreakpoints.isWideLayout(width)" in widget
    assert "AppBreakpoints.isMobileLarge(width)" not in widget


def test_responsive_grid_cross_axis_count_uses_four_bands() -> None:
    small, large, tablet, desktop = responsive_grid_cross_axis_count(2, child_count=6)
    assert (small, large, tablet, desktop) == (1, 2, 3, 4)
    expr = grid_cross_axis_count_expr(small, large, tablet, desktop)
    assert "isMobileLarge(width)" in expr
    assert "isMobileSmall" not in expr
