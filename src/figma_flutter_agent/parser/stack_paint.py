"""Stack child paint order for absolute (Positioned) layouts."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _stack_child_area(node: CleanDesignTreeNode) -> float:
    return (node.sizing.width or 0.0) * (node.sizing.height or 0.0)


def sort_absolute_stack_children(
    children: list[CleanDesignTreeNode],
    *,
    is_layout_root: bool = False,
) -> list[CleanDesignTreeNode]:
    """Order Stack children for painting.

    Nested absolute stacks keep Figma sibling order. Only the layout root may move
    large VECTOR/IMAGE backdrops before foreground siblings.
    """
    if not children or not all(child.stack_placement is not None for child in children):
        return children
    if not is_layout_root:
        return children

    total_area = sum(_stack_child_area(child) for child in children)
    if total_area <= 0.0:
        return children

    backdrop_types = frozenset({NodeType.VECTOR, NodeType.IMAGE})
    area_threshold = total_area * 0.2
    backdrops = [
        child
        for child in children
        if child.type in backdrop_types and _stack_child_area(child) >= area_threshold
    ]
    if not backdrops:
        return children

    backdrop_ids = {child.id for child in backdrops}
    backdrops_sorted = sorted(backdrops, key=lambda child: -_stack_child_area(child))
    foreground = [child for child in children if child.id not in backdrop_ids]
    return [*backdrops_sorted, *foreground]


def _all_children_positioned(children: list[CleanDesignTreeNode]) -> bool:
    return bool(children) and all(child.stack_placement is not None for child in children)


def apply_stack_paint_order_to_clean_tree(root: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Reorder absolute STACK children so large backdrops paint under foreground UI."""

    def walk(node: CleanDesignTreeNode, *, is_screen_root: bool) -> CleanDesignTreeNode:
        children = [walk(child, is_screen_root=False) for child in node.children]
        if node.type == NodeType.STACK and _all_children_positioned(children):
            children = sort_absolute_stack_children(children, is_layout_root=is_screen_root)
        return node.model_copy(update={"children": children})

    return walk(root, is_screen_root=True)
