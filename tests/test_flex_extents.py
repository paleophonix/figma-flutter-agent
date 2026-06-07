"""Universal flex extent law: no infinite cross-axis in unbounded flex hosts."""

import json
import re
from pathlib import Path

from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.generator.layout.widgets.render import render_node_body
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    LayoutSlotIr,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    WrapKind,
)

_BACKGROUND_DUMP = Path(
    r"e:\@dev\flutter-demo-project\demo_app\.figma_debug\raw\background_layout.json"
)


def test_compact_icon_button_in_row_avoids_infinite_height() -> None:
    icon = CleanDesignTreeNode(
        id="btn",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=48.0, height=48.0),
        style=NodeStyle(
            background_color="0xFFF6F6F2",
            border_radius=18.0,
            border_width=1.0,
            border_color="0xFFF6F6F2",
            has_stroke=True,
        ),
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="Icon",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
                children=[],
            )
        ],
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Toolbar",
        type=NodeType.ROW,
        sizing=Sizing(width=191.0, height=48.0),
        children=[icon],
    )
    body = render_node_body(row, uses_svg=False)
    assert "height: double.infinity" not in body
    assert "SizedBox(width: 48.0, height: 48.0" in body


def test_row_cross_stretch_height_uses_figma_height_not_infinity() -> None:
    child = CleanDesignTreeNode(
        id="chip",
        name="Chip",
        type=NodeType.CONTAINER,
        sizing=Sizing(height_mode=SizingMode.FILL, width=80.0, height=36.0),
        layout_slot=LayoutSlotIr(wraps=(WrapKind.CROSS_STRETCH_HEIGHT,)),
        children=[],
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width=300.0, height=48.0),
        children=[child],
    )
    body = render_node_body(row, uses_svg=False)
    assert "height: double.infinity" not in body
    assert "height: 36.0" in body


def test_flexible_is_never_wrapped_by_sized_box() -> None:
    child = CleanDesignTreeNode(
        id="chip",
        name="Chip",
        type=NodeType.BUTTON,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=48.0, height=48.0),
        layout_slot=LayoutSlotIr(wraps=(WrapKind.FLEXIBLE_LOOSE,)),
        style=NodeStyle(
            background_color="0xFFF6F6F2",
            border_radius=18.0,
            border_width=1.0,
            border_color="0xFFF6F6F2",
            has_stroke=True,
        ),
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="Icon",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
                children=[],
            )
        ],
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Toolbar",
        type=NodeType.ROW,
        sizing=Sizing(width=191.0, height=48.0),
        children=[child],
    )
    body = render_node_body(row, uses_svg=False)
    assert "SizedBox(child: Flexible(" not in body
    assert re.search(r"SizedBox\([^)]*child:\s*Flexible\(", body) is None
    assert "Flexible(fit: FlexFit.loose, flex: 0, child: SizedBox(" in body


def test_row_child_stack_height_pin_ignores_nested_overflow_box() -> None:
    """Nested positioned-slot OverflowBox must not block outer ROW height pins."""
    date = CleanDesignTreeNode(
        id="date",
        name="Date",
        type=NodeType.TEXT,
        text="Today, 11:42",
        sizing=Sizing(width=86.0, height=18.0),
        children=[],
    )
    badge = CleanDesignTreeNode(
        id="badge",
        name="Badge",
        type=NodeType.ROW,
        sizing=Sizing(width=24.0, height=25.0),
        children=[],
    )
    meta_stack = CleanDesignTreeNode(
        id="meta",
        name="Meta",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=85.0,
            height=50.5,
        ),
        layout_slot=LayoutSlotIr(wraps=(WrapKind.CONSTRAINED_BOX,)),
        children=[date, badge],
    )
    row = CleanDesignTreeNode(
        id="row",
        name="CardRow",
        type=NodeType.ROW,
        sizing=Sizing(width=280.0, height=97.0, height_mode=SizingMode.FILL),
        children=[meta_stack],
    )
    body = render_node_body(row, uses_svg=False)
    assert "SizedBox(width: 85.0, height: 50.5, child: Stack(" in body
    assert "maxHeight: double.infinity" not in body


def test_background_emit_has_no_infinite_height_in_flex() -> None:
    if not _BACKGROUND_DUMP.is_file():
        return
    raw = json.loads(_BACKGROUND_DUMP.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(raw)
    root = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=False,
        project_dir=_BACKGROUND_DUMP.parent.parent.parent,
    )
    layout = render_layout_file(
        root,
        feature_name="background",
        uses_svg=True,
        use_geometry_planner=True,
    )["lib/generated/background_layout.dart"]
    assert "height: double.infinity" not in layout
    assert re.search(r"SizedBox\([^)]*child:\s*Flexible\(", layout) is None
