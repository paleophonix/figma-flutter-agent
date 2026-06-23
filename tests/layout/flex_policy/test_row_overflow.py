"""Regression tests for LAW-ROW-CHILD-OVERFLOW: rigid row children overflow guard."""

from figma_flutter_agent.generator.layout.flex_policy.row import (
    apply_row_rigid_overflow_relief,
    row_rigid_main_axis_overflow,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
)


def _make_row_with_rigid_children(
    row_width: float,
    child_widths: list[float],
    *,
    spacing: float = 0.0,
) -> CleanDesignTreeNode:
    """Build a minimal ROW node with fixed-width children."""
    children = [
        CleanDesignTreeNode(
            id=f"1:child{i}",
            name=f"Child{i}",
            type=NodeType.CONTAINER,
            sizing=Sizing(width=w, height=20.0),
        )
        for i, w in enumerate(child_widths)
    ]
    return CleanDesignTreeNode(
        id="1:row",
        name="TestRow",
        type=NodeType.ROW,
        spacing=spacing,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=row_width, height=20.0),
        children=children,
    )


def test_row_children_dont_overflow() -> None:
    """Verifies that a row with children whose total width exceeds parent
    constraint is emitted with Flexible wrappers, preventing RenderFlex overflow."""
    row = _make_row_with_rigid_children(327.0, [120.0, 120.0, 90.0])
    overflow = row_rigid_main_axis_overflow(row)
    assert overflow > 0, f"Expected overflow > 0, got {overflow}"

    child_widgets = [
        "SizedBox(width: 120.0, child: Placeholder())",
        "SizedBox(width: 120.0, child: Placeholder())",
        "SizedBox(width: 90.0, child: Placeholder())",
    ]
    result = apply_row_rigid_overflow_relief(row, child_widgets)

    assert len(result) == 3
    assert any("Expanded(child:" in w for w in result), (
        f"Expected at least one child wrapped in Expanded, got: {result}"
    )


def test_row_children_dont_overflow_with_gap() -> None:
    """Overflow detection must account for spacing between children."""
    row = _make_row_with_rigid_children(300.0, [100.0, 100.0, 100.0], spacing=5.0)
    overflow = row_rigid_main_axis_overflow(row)
    assert overflow > 0

    child_widgets = [
        "SizedBox(width: 100.0)",
        "SizedBox(width: 100.0)",
        "SizedBox(width: 100.0)",
    ]
    result = apply_row_rigid_overflow_relief(row, child_widgets)
    assert any("Expanded(child:" in w for w in result)


def test_no_relief_when_children_fit() -> None:
    """Children that fit within the row must not be wrapped."""
    row = _make_row_with_rigid_children(300.0, [100.0, 100.0])
    overflow = row_rigid_main_axis_overflow(row)
    assert overflow <= 0

    child_widgets = ["SizedBox(width: 100.0)", "SizedBox(width: 100.0)"]
    result = apply_row_rigid_overflow_relief(row, child_widgets)
    assert result == child_widgets


def test_already_flex_children_not_double_wrapped() -> None:
    """Children already wrapped in Expanded/Flexible must not receive a second wrapper."""
    row = _make_row_with_rigid_children(300.0, [200.0, 200.0])
    child_widgets = [
        "Expanded(child: SizedBox(width: 200.0))",
        "SizedBox(width: 200.0)",
    ]
    result = apply_row_rigid_overflow_relief(row, child_widgets)
    assert result[0] == "Expanded(child: SizedBox(width: 200.0))"
    assert "Expanded(child:" in result[1]


def test_overflow_detected_with_fill_sibling() -> None:
    """Overflow detection must not bail out when a FILL sibling coexists with rigid children."""
    children = [
        CleanDesignTreeNode(
            id="1:rigid",
            name="Rigid",
            type=NodeType.CONTAINER,
            sizing=Sizing(width=250.0, height=18.0),
        ),
        CleanDesignTreeNode(
            id="1:fill",
            name="Fill",
            type=NodeType.CONTAINER,
            sizing=Sizing(width_mode=SizingMode.FILL, width=0.0, height=18.0),
        ),
    ]
    row = CleanDesignTreeNode(
        id="1:row",
        name="TestRow",
        type=NodeType.ROW,
        spacing=0.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=200.0, height=18.0),
        children=children,
    )
    overflow = row_rigid_main_axis_overflow(row)
    assert overflow > 0, (
        f"Expected overflow > 0 when rigid child (250) exceeds row (200), got {overflow}"
    )


def test_relief_wraps_rigid_child_despite_fill_sibling() -> None:
    """Rigid child that overflows must be wrapped in Flexible even with a FILL sibling."""
    children = [
        CleanDesignTreeNode(
            id="1:rigid",
            name="Rigid",
            type=NodeType.CONTAINER,
            sizing=Sizing(width=250.0, height=18.0),
        ),
        CleanDesignTreeNode(
            id="1:fill",
            name="Fill",
            type=NodeType.CONTAINER,
            sizing=Sizing(width_mode=SizingMode.FILL, width=0.0, height=18.0),
        ),
    ]
    row = CleanDesignTreeNode(
        id="1:row",
        name="TestRow",
        type=NodeType.ROW,
        spacing=0.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=200.0, height=18.0),
        children=children,
    )
    child_widgets = [
        "SizedBox(width: 250.0, child: Placeholder())",
        "Expanded(child: SizedBox(width: 0.0, child: Placeholder()))",
    ]
    result = apply_row_rigid_overflow_relief(row, child_widgets)
    assert len(result) == 2
    assert result[1] == child_widgets[1], "FILL child (already Expanded) should not be re-wrapped"
    assert "Expanded(child:" in result[0], (
        f"Rigid overflow child should be wrapped in Expanded, got: {result[0]}"
    )
