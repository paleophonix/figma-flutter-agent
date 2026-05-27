from figma_flutter_agent.parser.accessibility import (
    collect_accessibility_warnings,
    contrast_ratio,
    derive_accessibility_label,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType


def test_contrast_ratio_for_black_on_white() -> None:
    assert contrast_ratio("0xFF000000", "0xFFFFFFFF") == 21.0


def test_derive_accessibility_label_uses_child_text_for_button() -> None:
    label = derive_accessibility_label(
        node_name="Primary Button",
        node_type=NodeType.BUTTON,
        text=None,
        children=[CleanDesignTreeNode(id="1:2", name="Label", type=NodeType.TEXT, text="Submit")],
    )

    assert label == "Submit"


def test_collect_accessibility_warnings_flags_low_contrast_and_small_font() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.COLUMN,
        style=NodeStyle(background_color="0xFFFFFFFF"),
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Caption",
                type=NodeType.TEXT,
                text="Hello",
                style=NodeStyle(text_color="0xFFCCCCCC", font_size=10),
            )
        ],
    )

    warnings = collect_accessibility_warnings(root)

    assert len(warnings) == 2
    assert any("Low contrast" in warning for warning in warnings)
    assert any("Small font size" in warning for warning in warnings)
