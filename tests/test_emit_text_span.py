from figma_flutter_agent.generator.emit_text_span import emit_text_rich
from figma_flutter_agent.generator.llm_dart import _patch_stack_filled_buttons_from_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    StackPlacement,
    TextSpanPart,
)


def test_emit_text_rich_children_are_bracket_safe() -> None:
    widget = emit_text_rich(
        [
            "TextSpan(text: 'A', style: Theme.of(context).textTheme.bodyLarge?.copyWith("
            "color: Color(0xFF000000), fontSize: 14.0))",
            "TextSpan(text: 'B', style: Theme.of(context).textTheme.bodyLarge)",
        ],
        text_align_suffix=", textAlign: TextAlign.left",
        include_text_scaler=False,
    )
    assert widget.count("[") == widget.count("]")
    assert "Text.rich(TextSpan(children:" in widget


def test_emit_text_rich_with_scaler_uses_multiline_form() -> None:
    widget = emit_text_rich(
        ["TextSpan(text: 'A', style: Theme.of(context).textTheme.bodyLarge)"],
        text_align_suffix=", textAlign: TextAlign.center",
        include_text_scaler=True,
    )
    assert "textScaler: textScaler" in widget
    assert "Text.rich(\n" in widget
    assert "TextSpan(children:" in widget


def test_patch_stack_filled_preserves_copywith_fields() -> None:
    screen = (
        "Positioned(child: InkWell(child: Text.rich(TextSpan(children: ["
        "TextSpan(text: 'LOG IN', style: Theme.of(context).textTheme.bodyLarge?.copyWith("
        "color: Color(0xFF000000), fontSize: 14.0, fontWeight: FontWeight.w700)"
        ")]))))"
    )
    fill = CleanDesignTreeNode(
        id="1:fill",
        name="fill",
        type=NodeType.CONTAINER,
        style=NodeStyle(background_color="#8E97FD"),
        stack_placement=StackPlacement(top=0.0, left=0.0, width=374.0, height=63.0),
        children=[],
    )
    label = CleanDesignTreeNode(
        id="1:label",
        name="label",
        type=NodeType.TEXT,
        text="LOG IN",
        style=NodeStyle(text_color="#FFFFFF"),
        stack_placement=StackPlacement(top=10.0, left=10.0, width=100.0, height=14.0),
        children=[],
    )
    stack = CleanDesignTreeNode(
        id="1:stack",
        name="stack",
        type=NodeType.STACK,
        children=[fill, label],
    )
    root = CleanDesignTreeNode(id="1:root", name="root", type=NodeType.STACK, children=[stack])
    patched = _patch_stack_filled_buttons_from_tree(screen, root)
    assert "fontSize: 14.0" in patched
    assert "))), fontSize" not in patched
