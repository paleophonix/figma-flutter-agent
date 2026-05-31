"""Stack child paint order for absolute (Positioned) layouts."""

from __future__ import annotations

from figma_flutter_agent.parser.overlap_sweep import demote_overlapping_occluders
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _stack_child_area(node: CleanDesignTreeNode) -> float:
    return (node.sizing.width or 0.0) * (node.sizing.height or 0.0)


def _is_bottom_screen_chrome(node: CleanDesignTreeNode) -> bool:
    """Bottom tab bars and home indicators should paint above scrollable content."""
    from figma_flutter_agent.parser.interaction import looks_like_checkbox_control

    if looks_like_checkbox_control(node):
        return False
    placement = node.stack_placement
    if placement is None:
        return False
    top = placement.top or 0.0
    width = node.sizing.width or placement.width or 0.0
    height = placement.height or node.sizing.height or 0.0
    if width > 0.0 and height > 0.0 and width < 48.0 and height < 48.0:
        return False
    if top < 680.0 or height > 160.0:
        return False
    if node.type == NodeType.BOTTOM_NAV:
        return True
    lowered = node.name.lower()
    if any(token in lowered for token in ("bottom", "tab bar", "navigation", "home indicator")):
        return True
    if node.type != NodeType.CONTAINER:
        return False
    if height > 130.0:
        return False
    return bool(node.style.background_color or node.style.effects)


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
    children = demote_overlapping_occluders(children)
    chrome = [child for child in children if _is_bottom_screen_chrome(child)]
    if chrome:
        chrome_ids = {child.id for child in chrome}
        children = [child for child in children if child.id not in chrome_ids]
    else:
        chrome_ids = set()

    if not is_layout_root:
        return [*children, *chrome]

    total_area = sum(_stack_child_area(child) for child in children)
    if total_area <= 0.0:
        return [*children, *chrome]

    backdrop_types = frozenset({NodeType.VECTOR, NodeType.IMAGE})
    area_threshold = total_area * 0.2
    backdrops = [
        child
        for child in children
        if child.type in backdrop_types and _stack_child_area(child) >= area_threshold
    ]
    if not backdrops:
        return [*children, *chrome]

    backdrop_ids = {child.id for child in backdrops}
    backdrops_sorted = sorted(backdrops, key=lambda child: -_stack_child_area(child))
    foreground = [child for child in children if child.id not in backdrop_ids]
    return [*backdrops_sorted, *foreground, *chrome]


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
