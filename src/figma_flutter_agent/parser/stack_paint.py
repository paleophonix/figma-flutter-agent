"""Stack child paint order for absolute (Positioned) layouts."""

from __future__ import annotations

from figma_flutter_agent.parser.overlap_sweep import demote_overlapping_occluders
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _stack_child_area(node: CleanDesignTreeNode) -> float:
    return (node.sizing.width or 0.0) * (node.sizing.height or 0.0)


def _is_bottom_nav_background_shell(node: CleanDesignTreeNode) -> bool:
    """Wide bottom bar fill that must sit under tab icons, not over them."""
    placement = node.stack_placement
    if placement is None or node.type != NodeType.CONTAINER:
        return False
    width = node.sizing.width or placement.width or 0.0
    height = node.sizing.height or placement.height or 0.0
    top = placement.top if placement.top is not None else 0.0
    return (
        width >= 320.0
        and 72.0 <= height <= 140.0
        and top >= 680.0
        and bool(node.style.background_color or node.style.effects)
    )


def _is_bottom_nav_interactive(node: CleanDesignTreeNode) -> bool:
    """Tab icon rows/clusters that must paint above the bottom bar fill."""
    from figma_flutter_agent.parser.interaction import looks_like_checkbox_control

    if looks_like_checkbox_control(node):
        return False
    placement = node.stack_placement
    if placement is None:
        return False
    top = placement.top if placement.top is not None else 0.0
    width = node.sizing.width or placement.width or 0.0
    height = node.sizing.height or placement.height or 0.0
    if top < 760.0:
        return False
    if node.type == NodeType.BOTTOM_NAV:
        return True
    if width >= 320.0:
        return False
    if node.type == NodeType.STACK and height <= 72.0 and width <= 220.0:
        return True
    if node.extracted_widget_ref:
        return height <= 80.0
    return False


def _is_bottom_screen_chrome(node: CleanDesignTreeNode) -> bool:
    """Bottom tab bars and home indicators should paint above scrollable content."""
    return _is_bottom_nav_background_shell(node) or _is_bottom_nav_interactive(node)


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
    nav_backgrounds = [child for child in children if _is_bottom_nav_background_shell(child)]
    nav_interactive = [child for child in children if _is_bottom_nav_interactive(child)]
    nav_ids = {item.id for item in (*nav_backgrounds, *nav_interactive)}
    children = [child for child in children if child.id not in nav_ids]

    if not is_layout_root:
        return [*children, *nav_backgrounds, *nav_interactive]

    total_area = sum(_stack_child_area(child) for child in children)
    if total_area <= 0.0:
        return [*children, *nav_backgrounds, *nav_interactive]

    backdrop_types = frozenset({NodeType.VECTOR, NodeType.IMAGE})
    area_threshold = total_area * 0.2
    backdrops = [
        child
        for child in children
        if child.type in backdrop_types and _stack_child_area(child) >= area_threshold
    ]
    if not backdrops:
        return [*children, *nav_backgrounds, *nav_interactive]

    backdrop_ids = {child.id for child in backdrops}
    backdrops_sorted = sorted(backdrops, key=lambda child: -_stack_child_area(child))
    foreground = [child for child in children if child.id not in backdrop_ids]
    return [*backdrops_sorted, *foreground, *nav_backgrounds, *nav_interactive]


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
