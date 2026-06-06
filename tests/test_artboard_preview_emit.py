"""Artboard preview guard must not call fromEnvironment inside LayoutBuilder."""

from figma_flutter_agent.generator.layout.common import wrap_artboard_preview_layout_builder
from figma_flutter_agent.generator.layout.renderer import render_widget_file


def test_wrap_artboard_preview_uses_class_static_fields() -> None:
    wrapped = wrap_artboard_preview_layout_builder(
        preview_child="SizedBox(width: _artboardPreviewWidth, height: _artboardPreviewHeight, child: child)",
        fallback="child",
    )
    assert "_artboardPreviewWidth" in wrapped
    assert "ClipRect(child: SizedBox(" in wrapped
    assert "double.fromEnvironment" not in wrapped
    assert "String.fromEnvironment" not in wrapped


def test_render_layout_file_emits_artboard_preview_fields_for_decomposed_stack() -> None:
    from figma_flutter_agent.generator.layout.renderer import render_layout_file
    from figma_flutter_agent.schemas import (
        CleanDesignTreeNode,
        NodeType,
        Sizing,
        SizingMode,
        StackPlacement,
    )

    tree = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:body",
                name="Body",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, height=700.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:text",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Title",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:nav",
                name="Nav",
                type=NodeType.BOTTOM_NAV,
                sizing=Sizing(width=390.0, height=138.0),
                stack_placement=StackPlacement(left=0.0, bottom=0.0, width=390.0, height=138.0),
            ),
        ],
    )
    source = render_layout_file(
        tree,
        feature_name="preview_stack",
        uses_svg=False,
        use_geometry_planner=False,
    )["lib/generated/preview_stack_layout.dart"]
    assert "static final double _artboardPreviewWidth" in source
    assert "double.fromEnvironment" not in source


def test_layout_class_emits_artboard_preview_fields_when_guard_present() -> None:
    body = wrap_artboard_preview_layout_builder(
        preview_child="SizedBox(width: _artboardPreviewWidth, height: _artboardPreviewHeight, child: child)",
        fallback="child",
    )
    source = render_widget_file(
        class_name="DemoLayout",
        body=body,
        uses_svg=False,
        use_package_imports=False,
        source_file="lib/generated/demo_layout.dart",
    )
    assert "static final double _artboardPreviewWidth" in source
    assert "String.fromEnvironment('FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH')" in source
