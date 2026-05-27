"""Tests for automatic accessibility fixes on clean design trees."""

from figma_flutter_agent.parser.accessibility import (
    apply_accessibility_fixes,
    collect_accessibility_warnings,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType


def test_apply_accessibility_fixes_bumps_font_and_contrast() -> None:
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

    fixed = apply_accessibility_fixes(root)
    text = fixed.children[0]

    assert text.style.font_size == 12.0
    assert text.style.text_color == "0xFF000000"
    assert collect_accessibility_warnings(fixed) == []


def test_apply_accessibility_fixes_derives_button_label() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Submit Button",
        type=NodeType.BUTTON,
        children=[
            CleanDesignTreeNode(id="1:2", name="Label", type=NodeType.TEXT, text="Send"),
        ],
    )

    fixed = apply_accessibility_fixes(root)

    assert fixed.accessibility_label == "Send"


def test_apply_accessibility_fixes_preserves_skip_control_label_color() -> None:
    skip = CleanDesignTreeNode(
        id="1:1",
        name="Skip",
        type=NodeType.STACK,
        style=NodeStyle(background_color="0xFFFAF7F2"),
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Arrow",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_forward.svg",
                style=NodeStyle(has_stroke=True),
            ),
            CleanDesignTreeNode(
                id="1:3",
                name="15",
                type=NodeType.TEXT,
                text="15",
                style=NodeStyle(text_color="0xFFA0A3B1", font_size=12.0),
            ),
        ],
    )

    fixed = apply_accessibility_fixes(skip)

    assert fixed.children[1].style.text_color == "0xFFA0A3B1"
