"""IR guard placement preservation under pixel fidelity profile (Wave E / U4)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.ir.validate import apply_ir_guards
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def test_apply_ir_guards_skips_viewport_clamp_when_preserve_placement() -> None:
    chrome = CleanDesignTreeNode(
        id="chrome",
        name="Chrome",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=120.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            left=0.0,
            top=800.0,
            width=390.0,
            height=120.0,
        ),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[chrome],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[WidgetIrNode(figma_id="chrome", kind=WidgetIrKind.COLUMN)],
        ),
    )
    guarded = apply_ir_guards(screen_ir, root, preserve_placement=True)
    child = guarded.children[0]
    assert child.stack_placement is not None
    assert child.stack_placement.top == 800.0


def test_apply_ir_guards_clamps_viewport_by_default() -> None:
    chrome = CleanDesignTreeNode(
        id="chrome",
        name="Chrome",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=120.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            left=0.0,
            top=800.0,
            width=390.0,
            height=120.0,
        ),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[chrome],
    )
    screen_ir = default_screen_ir(root)
    guarded = apply_ir_guards(screen_ir, root, preserve_placement=False)
    child = guarded.children[0]
    assert child.stack_placement is not None
    assert child.stack_placement.top != 800.0


def test_viewport_clamp_skips_tall_scroll_artboard_children() -> None:
    chrome = CleanDesignTreeNode(
        id="chrome",
        name="Adss",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=887.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            left=0.0,
            top=1020.0,
            width=375.0,
            height=887.0,
        ),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=1483.0),
        children=[chrome],
    )
    screen_ir = default_screen_ir(root)
    guarded = apply_ir_guards(screen_ir, root, preserve_placement=False)
    child = guarded.children[0]
    assert child.stack_placement is not None
    assert child.stack_placement.top == 1020.0


def test_viewport_clamp_preserves_outward_glow_bleed() -> None:
    """Atmospheric glow layers may extend above the artboard without viewport clamp."""
    from figma_flutter_agent.generator.ir.validate.viewport import _clamp_viewport_bounds
    from figma_flutter_agent.schemas import GradientFill, GradientStop, NodeStyle

    glow = CleanDesignTreeNode(
        id="glow",
        name="Light",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/light.svg",
        image_asset_key="assets/images/light.png",
        sizing=Sizing(width=428.5, height=432.4),
        style=NodeStyle(
            layer_blur=63.7,
            gradient=GradientFill(
                type="linear",
                stops=[GradientStop(position=0.0, color="0x00FFFFFF")],
            ),
        ),
        stack_placement=StackPlacement(
            left=100.0,
            top=-121.1,
            width=428.5,
            height=432.4,
        ),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[glow],
    )
    tree_by_id = {root.id: root, glow.id: glow}
    parent_by_id = {glow.id: root.id}
    changed = _clamp_viewport_bounds(
        glow,
        viewport_width=375.0,
        viewport_height=812.0,
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    )
    assert not changed
    assert glow.stack_placement is not None
    assert glow.stack_placement.top == -121.1


def test_viewport_clamp_preserves_right_peek_tab_geometry() -> None:
    """Law: artboard_peek_child_must_clip_not_squeeze — IR guard must not shift peek tabs."""
    from figma_flutter_agent.generator.ir.validate.viewport import (
        _clamp_viewport_bounds,
        _validate_viewport_bounds,
    )

    peek_tab = CleanDesignTreeNode(
        id="peek-tab",
        name="Tab / Disable",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=44.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            left=360.0,
            top=117.0,
            right=-85.0,
            width=100.0,
            height=44.0,
        ),
        children=[],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[peek_tab],
    )
    tree_by_id = {root.id: root, peek_tab.id: peek_tab}
    parent_by_id = {peek_tab.id: root.id}
    changed = _clamp_viewport_bounds(
        peek_tab,
        viewport_width=375.0,
        viewport_height=812.0,
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    )
    assert not changed
    assert peek_tab.stack_placement is not None
    assert peek_tab.stack_placement.left == 360.0
    assert peek_tab.stack_placement.width == 100.0
    _validate_viewport_bounds(
        peek_tab,
        viewport_width=375.0,
        viewport_height=812.0,
        root_id=root.id,
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    )
