"""Nested frame responsive reflow (spec §7.3)."""

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_nested_column_reflows_inside_parent_column() -> None:
    """A nested Column with 2–4 children reflows on tablet/desktop."""
    section = CleanDesignTreeNode(
        id="2",
        name="Section",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="3", name="Left", type=NodeType.TEXT, text="Left"),
            CleanDesignTreeNode(id="4", name="Right", type=NodeType.TEXT, text="Right"),
        ],
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            section,
            CleanDesignTreeNode(id="5", name="Footer", type=NodeType.TEXT, text="Footer"),
        ],
    )

    layout = render_layout_file(screen, feature_name="nested_section", uses_svg=False)[
        "lib/generated/nested_section_layout.dart"
    ]

    assert layout.count("LayoutBuilder(") >= 2
    assert "AppBreakpoints.isWideLayout(width)" in layout


def test_nested_column_skipped_inside_row_parent() -> None:
    """Rows do not trigger nested column reflow (only one level of column split)."""
    section = CleanDesignTreeNode(
        id="2",
        name="Section",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="3", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(id="4", name="B", type=NodeType.TEXT, text="B"),
        ],
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.ROW,
        children=[section],
    )

    layout = render_layout_file(screen, feature_name="row_parent", uses_svg=False)[
        "lib/generated/row_parent_layout.dart"
    ]

    assert "LayoutBuilder(" not in layout
