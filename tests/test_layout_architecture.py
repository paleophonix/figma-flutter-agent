"""Architecture guards for deterministic layout codegen."""

from figma_flutter_agent.generator.layout.renderer import (
    _plan_layout_methods,
    _tree_depth,
    body_needs_dart_ui,
    body_needs_text_scaler,
    render_layout_file,
    render_widget_file,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def _chain(depth: int, *, leaf_type: NodeType = NodeType.CONTAINER) -> CleanDesignTreeNode:
    node = CleanDesignTreeNode(
        id="leaf",
        name="Leaf",
        type=leaf_type,
        style=NodeStyle(),
        sizing=Sizing(width=10, height=10),
    )
    for index in range(depth - 1):
        node = CleanDesignTreeNode(
            id=f"n{index}",
            name=f"Level{index}",
            type=NodeType.COLUMN,
            style=NodeStyle(),
            sizing=Sizing(width=100, height=100),
            children=[node],
        )
    return node


def test_body_needs_text_scaler_detects_text_widgets() -> None:
    assert body_needs_text_scaler("const SizedBox.shrink()") is False
    assert body_needs_text_scaler("Text('hi', textScaler: textScaler)") is True
    assert body_needs_text_scaler("TextField(decoration: InputDecoration())") is True


def test_render_widget_file_omits_text_scaler_for_container_only() -> None:
    source = render_widget_file(
        class_name="DecorPanel",
        body="Container(color: Colors.red)",
        uses_svg=False,
    )
    assert "textScaler" not in source


def test_render_widget_file_includes_text_scaler_when_text_present() -> None:
    source = render_widget_file(
        class_name="LabelPanel",
        body="Text('Hello')",
        uses_svg=False,
    )
    assert "final textScaler = MediaQuery.textScalerOf(context);" in source


def test_render_widget_file_includes_dart_ui_for_blur() -> None:
    body = (
        "BackdropFilter("
        "filter: ImageFilter.blur(sigmaX: 12.0, sigmaY: 12.0), "
        "child: const SizedBox.shrink())"
    )
    assert body_needs_dart_ui(body)
    source = render_widget_file(
        class_name="BlurredChrome",
        body=body,
        uses_svg=False,
    )
    assert "import 'dart:ui' show ImageFilter;" in source


def test_deep_tree_generates_private_builder_methods() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        style=NodeStyle(),
        sizing=Sizing(width=400, height=800),
        children=[_chain(8) for _ in range(2)],
    )
    assert _tree_depth(root) > 7
    methods = _plan_layout_methods(root)
    assert methods is not None
    assert len(methods) == 2
    layout = render_layout_file(root, feature_name="deep", uses_svg=False)[
        "lib/generated/deep_layout.dart"
    ]
    assert "Widget _build" in layout
    assert methods[0].name in layout
