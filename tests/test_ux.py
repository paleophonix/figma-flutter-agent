from figma_flutter_agent.parser.ux import collect_ux_suggestions
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Padding, Sizing, SizingMode


def _button(width: float, height: float, name: str = "Continue") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="btn",
        name=name,
        type=NodeType.BUTTON,
        sizing=Sizing(
            width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED, width=width, height=height
        ),
    )


def test_collect_ux_suggestions_flags_small_touch_targets() -> None:
    root = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.CONTAINER,
        children=[_button(32, 32)],
    )

    suggestions = collect_ux_suggestions(root)

    assert any("48dp touch targets" in suggestion for suggestion in suggestions)


def test_collect_ux_suggestions_flags_deep_layout_trees() -> None:
    node: CleanDesignTreeNode = CleanDesignTreeNode(id="leaf", name="Leaf", type=NodeType.CONTAINER)
    for index in range(9):
        node = CleanDesignTreeNode(
            id=str(index),
            name=f"Level {index}",
            type=NodeType.CONTAINER,
            children=[node],
        )

    suggestions = collect_ux_suggestions(node)

    assert any("nesting depth" in suggestion for suggestion in suggestions)


def test_collect_ux_suggestions_flags_many_spacing_values() -> None:
    root = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.CONTAINER,
        spacing=4,
        padding=Padding(top=5, right=7, bottom=9, left=11),
        children=[
            CleanDesignTreeNode(id="2", name="A", type=NodeType.CONTAINER, spacing=13),
            CleanDesignTreeNode(id="3", name="B", type=NodeType.CONTAINER, spacing=17),
            CleanDesignTreeNode(id="4", name="C", type=NodeType.CONTAINER, spacing=19),
            CleanDesignTreeNode(id="5", name="D", type=NodeType.CONTAINER, spacing=23),
            CleanDesignTreeNode(id="6", name="E", type=NodeType.CONTAINER, spacing=29),
        ],
    )

    suggestions = collect_ux_suggestions(root)

    assert any("spacing values" in suggestion for suggestion in suggestions)
