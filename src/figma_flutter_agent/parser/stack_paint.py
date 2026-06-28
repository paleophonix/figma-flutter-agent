"""Stack child paint order for absolute (Positioned) layouts."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.geometry_facts import viewport_chrome_band_size
from figma_flutter_agent.parser.z_dag import z_dag_sort
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_BOTTOM_BAR_MIN_WIDTH_RATIO = 320.0 / 414.0
_BOTTOM_SHELL_TOP_RATIO = 680.0 / 896.0
_BOTTOM_INTERACTIVE_TOP_RATIO = 760.0 / 896.0
_DEFAULT_VIEWPORT_WIDTH = 414.0
_DEFAULT_VIEWPORT_HEIGHT = 896.0


_FULL_BLEED_BACKDROP_VIEWPORT_RATIO = 0.75


def _is_viewport_chrome_band_node(node: CleanDesignTreeNode) -> bool:
    """Full-bleed iOS/Android status and home-indicator chrome."""
    name = (node.name or "").strip()
    if not name.startswith("Native /"):
        return False
    if not viewport_chrome_band_size(node.sizing.width, node.sizing.height):
        return False
    placement = node.stack_placement
    if placement is None:
        return False
    return placement.vertical in {"TOP", "BOTTOM"}


def _is_full_bleed_vector_backdrop(
    node: CleanDesignTreeNode,
    *,
    viewport_width: float,
    viewport_height: float,
    area_threshold: float,
) -> bool:
    """Large flattened vector illustrations that must paint under foreground UI."""
    if node.type not in {NodeType.STACK, NodeType.CONTAINER}:
        return False
    if not node.vector_asset_key:
        return False
    area = _stack_child_area(node)
    if area <= 0.0:
        return False
    viewport_area = viewport_width * viewport_height
    if viewport_area > 0.0 and area >= viewport_area * _FULL_BLEED_BACKDROP_VIEWPORT_RATIO:
        return True
    return bool(node.render_boundary and area >= area_threshold)


def _viewport_size(
    children: list[CleanDesignTreeNode],
) -> tuple[float, float]:
    """Infer artboard size from the widest/tallest positioned child."""
    width = 0.0
    height = 0.0
    for child in children:
        placement = child.stack_placement
        if placement is None:
            continue
        right = placement.right
        left = placement.left or 0.0
        bottom = placement.bottom
        top = placement.top or 0.0
        child_width = child.sizing.width or placement.width or 0.0
        child_height = child.sizing.height or placement.height or 0.0
        if right is not None:
            width = max(width, right)
        elif child_width > 0:
            width = max(width, left + child_width)
        if bottom is not None:
            height = max(height, bottom)
        elif child_height > 0:
            height = max(height, top + child_height)
    if width <= 0.0:
        width = _DEFAULT_VIEWPORT_WIDTH
    if height <= 0.0:
        height = _DEFAULT_VIEWPORT_HEIGHT
    return width, height


def _stack_child_area(node: CleanDesignTreeNode) -> float:
    return (node.sizing.width or 0.0) * (node.sizing.height or 0.0)


def _is_root_content_sheet(
    node: CleanDesignTreeNode,
    *,
    viewport_width: float,
    viewport_height: float,
) -> bool:
    """Large rounded-top content panels that must paint under foreground tiles."""
    placement = node.stack_placement
    if placement is None or node.type not in {NodeType.CONTAINER, NodeType.STACK}:
        return False
    width = node.sizing.width or placement.width or 0.0
    height = node.sizing.height or placement.height or 0.0
    if width < viewport_width * 0.85 or height < viewport_height * 0.35:
        return False
    if not node.style.background_color:
        return False
    top = placement.top if placement.top is not None else 0.0
    if top > viewport_height * 0.35:
        return False
    corners = node.style.border_radius_corners
    if corners is not None and (float(corners.top_left) > 0.0 or float(corners.top_right) > 0.0):
        return True
    radius = node.style.border_radius
    return radius is not None and float(radius) >= 12.0


def _is_bottom_nav_background_shell(
    node: CleanDesignTreeNode,
    *,
    viewport_width: float,
    viewport_height: float,
) -> bool:
    """Wide bottom bar fill that must sit under tab icons, not over them."""
    placement = node.stack_placement
    if placement is None or node.type != NodeType.CONTAINER:
        return False
    width = node.sizing.width or placement.width or 0.0
    height = node.sizing.height or placement.height or 0.0
    top = placement.top if placement.top is not None else 0.0
    min_bar_width = viewport_width * _BOTTOM_BAR_MIN_WIDTH_RATIO
    min_top = viewport_height * _BOTTOM_SHELL_TOP_RATIO
    return (
        width >= min_bar_width
        and 72.0 <= height <= 140.0
        and top >= min_top
        and bool(node.style.background_color or node.style.effects)
    )


def _row_is_docked_bottom_icon_bar(
    node: CleanDesignTreeNode,
    *,
    viewport_height: float,
) -> bool:
    """Wide bottom rows of compact icon controls must paint above scroll bodies."""
    placement = node.stack_placement
    if placement is None or node.type != NodeType.ROW:
        return False
    top = placement.top if placement.top is not None else 0.0
    height = node.sizing.height or placement.height or 0.0
    min_interactive_top = viewport_height * _BOTTOM_INTERACTIVE_TOP_RATIO
    docked = placement.vertical == "BOTTOM" or top >= min_interactive_top
    if not docked or not (72.0 <= float(height) <= 140.0):
        return False
    compact_controls = 0
    for child in node.children:
        width = child.sizing.width or 0.0
        child_height = child.sizing.height or 0.0
        if 28.0 <= float(width) <= 56.0 and 28.0 <= float(child_height) <= 56.0:
            compact_controls += 1
    return compact_controls >= 4


def _is_bottom_nav_interactive(
    node: CleanDesignTreeNode,
    *,
    viewport_width: float,
    viewport_height: float,
) -> bool:
    """Tab icon rows/clusters that must paint above the bottom bar fill."""
    from figma_flutter_agent.parser.interaction import layout_fact_checkbox_control

    if layout_fact_checkbox_control(node):
        return False
    placement = node.stack_placement
    if placement is None:
        return False
    top = placement.top if placement.top is not None else 0.0
    width = node.sizing.width or placement.width or 0.0
    height = node.sizing.height or placement.height or 0.0
    min_interactive_top = viewport_height * _BOTTOM_INTERACTIVE_TOP_RATIO
    min_bar_width = viewport_width * _BOTTOM_BAR_MIN_WIDTH_RATIO
    if top < min_interactive_top and placement.vertical != "BOTTOM":
        return False
    if node.type == NodeType.BOTTOM_NAV:
        return True
    if _row_is_docked_bottom_icon_bar(node, viewport_height=viewport_height):
        return True
    if node.type == NodeType.ROW:
        from figma_flutter_agent.generator.layout.navigation.items import (
            row_hosts_compact_nav_tabs,
        )

        if row_hosts_compact_nav_tabs(node) and 72.0 <= float(height) <= 140.0:
            return True
    if width >= min_bar_width:
        return False
    if node.type == NodeType.STACK and height <= 72.0 and width <= 220.0:
        return True
    if node.extracted_widget_ref:
        return height <= 80.0
    return False


def _content_overlaps_bottom_nav_band(
    node: CleanDesignTreeNode,
    *,
    viewport_height: float,
) -> bool:
    """Return True when a positioned subtree intersects the docked bottom-nav band."""
    placement = node.stack_placement
    if placement is None:
        return False
    if _is_bottom_nav_background_shell(
        node,
        viewport_width=_DEFAULT_VIEWPORT_WIDTH,
        viewport_height=viewport_height,
    ) or _is_bottom_nav_interactive(
        node,
        viewport_width=_DEFAULT_VIEWPORT_WIDTH,
        viewport_height=viewport_height,
    ):
        return False
    top = placement.top if placement.top is not None else 0.0
    height = node.sizing.height or placement.height or 0.0
    if height <= 0.0:
        return False
    bottom = top + float(height)
    nav_start = viewport_height * _BOTTOM_SHELL_TOP_RATIO
    return top < nav_start + 112.0 and bottom > nav_start


def _is_bottom_screen_chrome(
    node: CleanDesignTreeNode,
    *,
    viewport_width: float = _DEFAULT_VIEWPORT_WIDTH,
    viewport_height: float = _DEFAULT_VIEWPORT_HEIGHT,
) -> bool:
    """Bottom tab bars and home indicators should paint above scrollable content."""
    return _is_bottom_nav_background_shell(
        node,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    ) or _is_bottom_nav_interactive(
        node,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )


def sort_absolute_stack_children(
    children: list[CleanDesignTreeNode],
    *,
    is_layout_root: bool = False,
) -> list[CleanDesignTreeNode]:
    """Order Stack children for painting.

    Nested absolute stacks keep Figma sibling order. Only the layout root may move
    large VECTOR/IMAGE backdrops before foreground siblings. Flow children without
    ``stack_placement`` keep their original order and paint before positioned layers.
    """
    if not children:
        return children
    flow = [child for child in children if child.stack_placement is None]
    positioned = [child for child in children if child.stack_placement is not None]
    if not positioned:
        return children
    sorted_positioned = _sort_positioned_stack_subset(
        positioned,
        is_layout_root=is_layout_root,
    )
    return [*flow, *sorted_positioned]


def _sort_positioned_stack_subset(
    children: list[CleanDesignTreeNode],
    *,
    is_layout_root: bool,
) -> list[CleanDesignTreeNode]:
    """Apply Z-order and backdrop demotion to an all-positioned child subset."""
    children = z_dag_sort(children)
    viewport_width, viewport_height = _viewport_size(children)
    nav_backgrounds = [
        child
        for child in children
        if _is_bottom_nav_background_shell(
            child,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
    ]
    nav_interactive = [
        child
        for child in children
        if _is_bottom_nav_interactive(
            child,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
    ]
    viewport_chrome = [child for child in children if _is_viewport_chrome_band_node(child)]
    nav_ids = {item.id for item in (*nav_backgrounds, *nav_interactive)}
    chrome_ids = {item.id for item in viewport_chrome}
    children = [
        child for child in children if child.id not in nav_ids and child.id not in chrome_ids
    ]

    if not is_layout_root:
        return [*children, *nav_backgrounds, *nav_interactive, *viewport_chrome]

    total_area = sum(_stack_child_area(child) for child in children)
    if total_area <= 0.0:
        return [*children, *nav_backgrounds, *nav_interactive, *viewport_chrome]

    backdrop_types = frozenset({NodeType.VECTOR, NodeType.IMAGE})
    area_threshold = total_area * 0.2
    backdrops = [
        child
        for child in children
        if (
            child.type in backdrop_types and _stack_child_area(child) >= area_threshold
        )
        or _is_full_bleed_vector_backdrop(
            child,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            area_threshold=area_threshold,
        )
    ]
    content_sheets = [
        child
        for child in children
        if _is_root_content_sheet(
            child,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
    ]
    backdrops_sorted = sorted(backdrops, key=lambda child: -_stack_child_area(child))
    content_sorted = sorted(content_sheets, key=lambda child: -_stack_child_area(child))
    demoted_ids = {child.id for child in (*backdrops, *content_sheets)}
    foreground = [child for child in children if child.id not in demoted_ids]
    overlap_content = [
        child
        for child in foreground
        if _content_overlaps_bottom_nav_band(child, viewport_height=viewport_height)
    ]
    overlap_ids = {item.id for item in overlap_content}
    non_overlap = [child for child in foreground if child.id not in overlap_ids]
    if not demoted_ids and not overlap_content:
        return [*children, *nav_backgrounds, *nav_interactive, *viewport_chrome]
    return [
        *backdrops_sorted,
        *content_sorted,
        *non_overlap,
        *nav_backgrounds,
        *overlap_content,
        *nav_interactive,
        *viewport_chrome,
    ]


def _has_positioned_children(children: list[CleanDesignTreeNode]) -> bool:
    return any(child.stack_placement is not None for child in children)


def apply_stack_paint_order_to_clean_tree(root: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Reorder absolute STACK children so large backdrops paint under foreground UI."""

    def walk(node: CleanDesignTreeNode, *, is_screen_root: bool) -> CleanDesignTreeNode:
        children = [walk(child, is_screen_root=False) for child in node.children]
        if node.type == NodeType.STACK and _has_positioned_children(children):
            children = sort_absolute_stack_children(children, is_layout_root=is_screen_root)
        return node.model_copy(update={"children": children})

    return walk(root, is_screen_root=True)
