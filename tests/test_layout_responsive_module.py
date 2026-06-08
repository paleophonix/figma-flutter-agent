"""Unit tests for layout_responsive helpers."""

from figma_flutter_agent.generator.layout.responsive import (
    responsive_emit_context,
    responsive_host_width_literal,
    responsive_layout_width_assignment,
    should_apply_responsive_column_reflow,
    should_responsive_reflow,
    wide_column_reflow_enabled,
    wrap_responsive_root_column,
)
from figma_flutter_agent.generator.layout.responsive_grid import (
    grid_cross_axis_count_expr,
    responsive_grid_cross_axis_count,
)
from figma_flutter_agent.schemas import NodeType, SizingMode


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


def test_responsive_layout_width_uses_host_constraints() -> None:
    assert responsive_layout_width_assignment(390.0) == "final width = constraints.maxWidth;"
    assert responsive_layout_width_assignment(600.0) == "final width = constraints.maxWidth;"


def test_wide_column_reflow_disabled_for_phone_artboard() -> None:
    assert wide_column_reflow_enabled(390.0) is False
    assert wide_column_reflow_enabled(481.0) is True


def test_wrap_responsive_root_column_skips_reflow_for_phone_artboard() -> None:
    widget = wrap_responsive_root_column(
        main_axis="MainAxisAlignment.start",
        cross_axis="CrossAxisAlignment.stretch",
        child_widgets=["Text('A')", "Text('B')"],
        design_artboard_width=390.0,
    )
    assert "LayoutBuilder(" not in widget
    assert "isWideLayout" not in widget


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


def test_responsive_host_width_literal_stretches_phone_artboard_caps() -> None:
    with responsive_emit_context(enabled=True, design_artboard_width=390.0):
        assert responsive_host_width_literal(390.0) == "double.infinity"
        assert responsive_host_width_literal(357.0) == "double.infinity"
        assert responsive_host_width_literal(120.0) == "120.0"
        assert (
            responsive_host_width_literal(390.0, width_mode=SizingMode.FILL)
            == "double.infinity"
        )
    assert responsive_host_width_literal(390.0) == "390.0"
