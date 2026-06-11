"""Unstacking pass: false STACK rows to ROW/WRAP."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.geometry import (
    _HEIGHT_DELTA_TOLERANCE_PX,
    _OVERLAP_TOLERANCE_PX,
    child_layout_width,
    child_layout_x,
    compute_flex_spacing,
    stack_children_overlap_on_x,
    vertical_extent_delta,
)
from figma_flutter_agent.generator.ir.passes.sync import (
    index_ir_nodes,
    ir_kind_for_node_type,
    update_clean_subtree,
    update_ir_subtree,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrLayoutHints,
    WidgetIrNode,
)


def _stack_has_protected_archetype(node: CleanDesignTreeNode) -> bool:
    """Return True when a stack encodes interaction chrome, not a false flex row."""
    from figma_flutter_agent.parser.interaction import (
        looks_like_back_nav_stack,
        looks_like_skip_control_stack,
        stack_interaction_kind,
    )

    if looks_like_back_nav_stack(node) or looks_like_skip_control_stack(node):
        return True
    return stack_interaction_kind(node) is not None


def _children_have_horizontal_layout(children: list[CleanDesignTreeNode]) -> bool:
    """Return True when every child exposes horizontal stack coordinates."""
    if len(children) < 2:
        return False
    for child in children:
        if child_layout_x(child) is None or child_layout_width(child) is None:
            return False
    return True


def _monotonic_horizontal_row(children: list[CleanDesignTreeNode]) -> bool:
    ordered = sorted(
        children,
        key=lambda child: child_layout_x(child) if child_layout_x(child) is not None else 0.0,
    )
    for index in range(len(ordered) - 1):
        if stack_children_overlap_on_x(ordered[index], ordered[index + 1]):
            return False
        left_x = child_layout_x(ordered[index])
        left_w = child_layout_width(ordered[index])
        right_x = child_layout_x(ordered[index + 1])
        if left_x is None or left_w is None or right_x is None:
            return False
        min_gap = right_x - (left_x + left_w)
        if min_gap < -_OVERLAP_TOLERANCE_PX:
            return False
    return True


def _should_unstack_stack(node: CleanDesignTreeNode) -> bool:
    if node.type != NodeType.STACK or len(node.children) < 2:
        return False
    if _stack_has_protected_archetype(node):
        return False
    if not _children_have_horizontal_layout(node.children):
        return False
    if vertical_extent_delta(node.children) > _HEIGHT_DELTA_TOLERANCE_PX:
        return False
    return _monotonic_horizontal_row(node.children)


def _target_row_type(
    node: CleanDesignTreeNode,
    *,
    spacing: float,
) -> NodeType:
    parent_width = node.sizing.width
    if parent_width is None and node.geometry_frame is not None:
        parent_width = node.geometry_frame.layout_rect.width
    if parent_width is None or parent_width <= 0:
        return NodeType.ROW
    total_children_width = sum(child_layout_width(child) or 0.0 for child in node.children)
    gaps = spacing * max(len(node.children) - 1, 0)
    if total_children_width + gaps > float(parent_width) + _OVERLAP_TOLERANCE_PX:
        return NodeType.WRAP
    return NodeType.ROW


def _clear_child_placements(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    cleared = [child.model_copy(update={"stack_placement": None}) for child in node.children]
    return node.model_copy(update={"children": cleared})


def _apply_unstack_to_clean(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    if not _should_unstack_stack(node):
        return node
    spacing = compute_flex_spacing(node.children) or 0.0
    target = _target_row_type(node, spacing=spacing)
    updated = _clear_child_placements(node)
    return updated.model_copy(
        update={
            "type": target,
            "spacing": spacing,
            "layout_positioning": "AUTO",
        },
    )


def _build_ir_unstack_updater(
    target_type: NodeType,
    spacing: float,
):
    def ir_updater(node: WidgetIrNode) -> WidgetIrNode:
        if node.kind == WidgetIrKind.STACK or node.kind == WidgetIrKind.AUTO:
            return _apply_unstack_to_ir(
                node,
                target_type=target_type,
                spacing=spacing,
            )
        return node

    return ir_updater


def _apply_unstack_to_ir(
    node: WidgetIrNode,
    *,
    target_type: NodeType,
    spacing: float,
) -> WidgetIrNode:
    kind = ir_kind_for_node_type(target_type.value)
    hints = WidgetIrLayoutHints(flex_spacing=spacing)
    return node.model_copy(update={"kind": kind, "layout_hints": hints})


def unstack_homogeneous_stack(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Transform false horizontal stacks into ROW/WRAP on both graphs."""
    ir_index = index_ir_nodes(screen_ir.root)
    stack_ids: list[str] = []

    def collect(node: CleanDesignTreeNode) -> None:
        if _should_unstack_stack(node):
            stack_ids.append(node.id)
        for child in node.children:
            collect(child)

    collect(clean_tree)

    updated_clean = clean_tree
    updated_ir = screen_ir
    for node_id in stack_ids:
        clean_node = _find_clean_node(updated_clean, node_id)
        if clean_node is None:
            continue
        spacing = compute_flex_spacing(clean_node.children) or 0.0
        target = _target_row_type(clean_node, spacing=spacing)

        def clean_updater(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
            return _apply_unstack_to_clean(node)

        updated_clean = update_clean_subtree(updated_clean, node_id, clean_updater)

        ir_node = ir_index.get(node_id)
        if ir_node is not None:
            updated_ir = updated_ir.model_copy(
                update={
                    "root": update_ir_subtree(
                        updated_ir.root,
                        node_id,
                        _build_ir_unstack_updater(target, spacing),
                    ),
                },
            )
            ir_index = index_ir_nodes(updated_ir.root)

    return updated_ir, updated_clean


def _find_clean_node(
    root: CleanDesignTreeNode,
    node_id: str,
) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_clean_node(child, node_id)
        if found is not None:
            return found
    return None
