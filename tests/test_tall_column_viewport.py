"""Tall phone column artboards scroll in browser viewports."""

from figma_flutter_agent.generator.artboard import is_tall_mobile_artboard
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
)


def test_is_tall_mobile_artboard_detects_extra_tall_frames() -> None:
    assert is_tall_mobile_artboard(390.0, 917.3) is True
    assert is_tall_mobile_artboard(390.0, 844.0) is False
    assert is_tall_mobile_artboard(600.0, 1200.0) is False


def test_tall_column_root_emits_scroll_with_artboard_preview() -> None:
    root = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=917.0),
        children=[
            CleanDesignTreeNode(
                id="1:body",
                name="Body",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, width=390.0, height=893.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:text",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Chats",
                    )
                ],
            )
        ],
    )
    layout = render_layout_file(
        root,
        feature_name="tall_column",
        uses_svg=False,
        responsive_enabled=True,
    )["lib/generated/tall_column_layout.dart"]
    assert "_artboardPreviewWidth" in layout
    assert "SingleChildScrollView(" in layout
    compact = layout.replace(" ", "")
    assert "SizedBox(width:constraints.maxWidth" in compact
    assert "constraints.maxWidth < 390" not in layout
    assert "MediaQuery.sizeOf(context).height" in layout
    assert "OverflowBox(" in layout
    assert "maxHeight: double.infinity" in layout
