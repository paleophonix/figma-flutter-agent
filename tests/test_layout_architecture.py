"""Architecture guards for deterministic layout codegen."""

from figma_flutter_agent.generator.background import partition_wallpaper_foreground_tree
from figma_flutter_agent.generator.layout import (
    body_needs_dart_ui,
    body_needs_text_scaler,
    render_layout_file,
    render_widget_file,
)
from figma_flutter_agent.generator.layout.file_methods import _tree_depth, plan_layout_methods
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


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


def test_render_widget_file_omits_unused_svg_and_theme_imports() -> None:
    """Law: widget_file_imports_match_emit_symbols."""
    source = render_widget_file(
        class_name="RightButtonWidget",
        body="Image.asset('assets/images/shape.png', width: 12.0, height: 12.0)",
        uses_svg=True,
    )
    assert "flutter_svg" not in source
    assert "app_colors.dart" not in source
    assert "app_spacing.dart" not in source


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
    methods = plan_layout_methods(root)
    assert methods is not None
    assert len(methods) == 2
    layout = render_layout_file(root, feature_name="deep", uses_svg=False)[
        "lib/generated/deep_layout.dart"
    ]
    assert "Widget _build" in layout
    assert methods[0].name in layout


def _ambient_wallpaper_ellipse(node_id: str, name: str) -> CleanDesignTreeNode:
    stem = node_id.replace(":", "_")
    return CleanDesignTreeNode(
        id=node_id,
        name=name,
        type=NodeType.VECTOR,
        sizing=Sizing(width=357.0, height=357.0),
        style=NodeStyle(background_color="0xFF94BCEB"),
        vector_asset_key=f"assets/icons/{stem}.svg",
        image_asset_key=f"assets/images/{stem}.png",
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(
            left=-200.0,
            top=-40.0,
            width=357.0,
            height=357.0,
        ),
    )


def test_wallpaper_partition_decomposed_methods_align_with_render_tree() -> None:
    """Law: layout_methods_planned_from_render_tree."""
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        style=NodeStyle(background_color="0xFFFFFFFF"),
        sizing=Sizing(width=375.0, height=812.0),
        children=[
            _ambient_wallpaper_ellipse("bg:1", "Ellipse 1"),
            _ambient_wallpaper_ellipse("bg:2", "Ellipse 2"),
            CleanDesignTreeNode(
                id="logo",
                name="Logo",
                type=NodeType.STACK,
                sizing=Sizing(width=128.0, height=23.0),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    horizontal="CENTER",
                    left=123.5,
                    top=76.0,
                    width=128.0,
                    height=23.0,
                ),
                children=[],
            ),
            _chain(9),
            CleanDesignTreeNode(
                id="status",
                name="Native / Status Bar",
                type=NodeType.STACK,
                sizing=Sizing(width=375.0, height=44.0),
                children=[],
            ),
        ],
    )
    assert _tree_depth(root) > 7
    render_tree, wallpaper_children, _ = partition_wallpaper_foreground_tree(root)
    assert len(wallpaper_children) == 2
    assert len(render_tree.children) == 3
    methods = plan_layout_methods(render_tree)
    assert methods is not None
    assert len(methods) == len(render_tree.children)
    assert {method.node.id for method in methods} == {child.id for child in render_tree.children}
    layout = render_layout_file(root, feature_name="wallpaper_shell", uses_svg=False)[
        "lib/generated/wallpaper_shell_layout.dart"
    ]
    assert "Widget _build" in layout
    assert "SingleChildScrollView(" in layout
    assert "_buildBackground(context)" in layout
    assert "left: -200" in layout or "left: -200.0" in layout
    host_stack = layout.split("LayoutBuilder(")[0]
    assert "Positioned.fill(" not in host_stack
