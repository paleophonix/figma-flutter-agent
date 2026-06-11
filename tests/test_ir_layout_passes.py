"""Unit tests for dual-graph IR layout passes."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
    WidgetIrKind,
)


def _stack_child(
    node_id: str,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    node_type: NodeType = NodeType.BUTTON,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=node_type,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=width,
            height=height,
        ),
        stack_placement=StackPlacement(left=left, top=top, width=width, height=height),
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=left, y=top, width=width, height=height),
        ),
    )


def _horizontal_chip_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="stack-row",
        name="chip-row",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=400.0, height=40.0),
        children=[
            _stack_child("c1", left=0.0, top=0.0, width=60.0, height=32.0),
            _stack_child("c2", left=68.0, top=0.0, width=60.0, height=32.0),
            _stack_child("c3", left=136.0, top=0.0, width=60.0, height=32.0),
        ],
    )


def test_unstack_converts_homogeneous_stack_to_row() -> None:
    clean = _horizontal_chip_stack()
    screen_ir = default_screen_ir(clean)
    updated_ir, updated_clean = apply_ir_layout_passes(
        screen_ir,
        clean,
        macro_height_threshold_px=900,
    )
    stack_node = _find_node(updated_clean, "stack-row")
    assert stack_node is not None
    assert stack_node.type in {NodeType.ROW, NodeType.WRAP}
    assert stack_node.spacing == 8.0
    for child_id in ("c1", "c2", "c3"):
        child = _find_node(updated_clean, child_id)
        assert child is not None
        assert child.stack_placement is None
    ir_node = _find_ir_node(updated_ir.root, "stack-row")
    assert ir_node is not None
    assert ir_node.kind in {WidgetIrKind.ROW, WidgetIrKind.WRAP}
    assert ir_node.layout_hints is not None
    assert ir_node.layout_hints.flex_spacing == 8.0


def test_scroll_host_not_injected_for_896px_root() -> None:
    clean = CleanDesignTreeNode(
        id="root",
        name="screen",
        type=NodeType.COLUMN,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=390.0,
            height=896.0,
        ),
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=0.0, y=0.0, width=390.0, height=896.0),
        ),
        children=[
            CleanDesignTreeNode(
                id="child",
                name="body",
                type=NodeType.TEXT,
                text="hello",
            ),
        ],
    )
    screen_ir = default_screen_ir(clean)
    _, updated_clean = apply_ir_layout_passes(
        screen_ir,
        clean,
        macro_height_threshold_px=900,
    )
    assert updated_clean.scroll_axis == "none"
    assert updated_clean.sizing.height_mode == SizingMode.FIXED


def test_unstack_wrap_when_overflow() -> None:
    children = [
        _stack_child(
            f"c{index}",
            left=float(index * 68),
            top=0.0,
            width=60.0,
            height=32.0,
        )
        for index in range(6)
    ]
    clean = CleanDesignTreeNode(
        id="stack-wrap",
        name="chip-wrap",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=40.0),
        children=children,
    )
    screen_ir = default_screen_ir(clean)
    _, updated_clean = apply_ir_layout_passes(
        screen_ir,
        clean,
        macro_height_threshold_px=900,
    )
    stack_node = _find_node(updated_clean, "stack-wrap")
    assert stack_node is not None
    assert stack_node.type == NodeType.WRAP
    assert stack_node.spacing == 8.0


def test_scroll_host_injected_above_threshold() -> None:
    clean = CleanDesignTreeNode(
        id="root",
        name="screen",
        type=NodeType.COLUMN,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=390.0,
            height=1200.0,
        ),
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=0.0, y=0.0, width=390.0, height=1200.0),
        ),
        children=[],
    )
    screen_ir = default_screen_ir(clean)
    from figma_flutter_agent.generator.ir.passes.scroll_host import inject_scroll_host

    updated_ir, updated_clean = inject_scroll_host(
        screen_ir,
        clean,
        macro_height_threshold_px=900,
        inject_at_root=True,
    )
    assert updated_clean.scroll_axis == "vertical"
    assert updated_clean.sizing.height_mode == SizingMode.HUG
    assert updated_ir.root.kind == WidgetIrKind.NAV_SCROLL_HOST


def test_scroll_host_injected_for_tall_stack_root() -> None:
    clean = CleanDesignTreeNode(
        id="root",
        name="screen",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=390.0,
            height=1200.0,
        ),
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=0.0, y=0.0, width=390.0, height=1200.0),
        ),
        children=[],
    )
    screen_ir = default_screen_ir(clean)
    from figma_flutter_agent.generator.ir.passes.scroll_host import inject_scroll_host

    updated_ir, updated_clean = inject_scroll_host(
        screen_ir,
        clean,
        macro_height_threshold_px=900,
        inject_at_root=True,
    )
    assert updated_clean.scroll_axis == "vertical"
    assert updated_clean.sizing.height_mode == SizingMode.HUG
    assert updated_clean.sizing.height == 1200.0
    assert updated_ir.root.kind == WidgetIrKind.NAV_SCROLL_HOST


def test_apply_ir_layout_passes_idempotent() -> None:
    clean = _horizontal_chip_stack()
    screen_ir = default_screen_ir(clean)
    first_ir, first_clean = apply_ir_layout_passes(
        screen_ir,
        clean,
        macro_height_threshold_px=900,
        inject_root_scroll_host=True,
    )
    second_ir, second_clean = apply_ir_layout_passes(
        first_ir,
        first_clean,
        macro_height_threshold_px=900,
        inject_root_scroll_host=True,
    )
    assert second_clean.model_dump() == first_clean.model_dump()
    assert second_ir.model_dump() == first_ir.model_dump()


def test_apply_layout_passes_to_context_updates_destination_trees() -> None:
    from figma_flutter_agent.config import Settings
    from figma_flutter_agent.generator.ir.passes.planner import apply_layout_passes_to_context
    from figma_flutter_agent.generator.planner.context import GenerationPlanContext
    from figma_flutter_agent.schemas import DesignTokens

    chip_stack = _horizontal_chip_stack()
    main_tree = CleanDesignTreeNode(
        id="main-root",
        name="main",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=844.0),
        children=[chip_stack],
    )
    dest_tree = CleanDesignTreeNode(
        id="dest-root",
        name="dest",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=844.0),
        children=[chip_stack.model_copy(deep=True)],
    )
    context = GenerationPlanContext(
        settings=Settings(),
        clean_tree=main_tree,
        tokens=DesignTokens(),
        resolved_feature="demo",
        node_id="main-root",
        cluster_summary={},
        destination_trees={"dest": dest_tree},
    )
    updated = apply_layout_passes_to_context(context)
    main_row = _find_node(updated.clean_tree, "stack-row")
    dest_row = _find_node(updated.destination_trees["dest"], "stack-row")
    assert main_row is not None
    assert main_row.type in {NodeType.ROW, NodeType.WRAP}
    assert dest_row is not None
    assert dest_row.type in {NodeType.ROW, NodeType.WRAP}


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def _find_ir_node(root, node_id: str):

    if root.figma_id == node_id:
        return root
    for child in root.children:
        found = _find_ir_node(child, node_id)
        if found is not None:
            return found
    return None
