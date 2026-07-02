"""Bottom navigation item and icon resolution."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.navigation.constants import (
    COMPACT_ICON_NAV_TAB_MAX,
    MAX_BOTTOM_NAV_HOST_HEIGHT,
    MAX_BOTTOM_NAV_ITEMS,
    MIN_BOTTOM_NAV_ITEMS,
    NAV_SHELL_MIN_WIDTH,
    PILL_NAV_MAX_HEIGHT,
    PILL_NAV_MAX_WIDTH,
    PILL_NAV_MIN_HEIGHT,
    PILL_NAV_MIN_WIDTH,
)
from figma_flutter_agent.generator.variant.state import (
    get_variant_property,
    variant_is_checked,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_NAV_ITEM_GENERIC_NAMES = frozenset(
    {"link", "tab", "item", "nav", "navitem", "container", "frame", "background"}
)
_NAV_ICON_FALLBACK = "const Icon(Icons.circle_outlined)"


def find_nav_chrome_background_shell(
    node: CleanDesignTreeNode,
) -> CleanDesignTreeNode | None:
    """Return the first descendant full-bleed painted bottom-nav dock shell."""

    def walk(candidate: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if _is_nav_chrome_background_shell(candidate):
            return candidate
        for child in candidate.children:
            found = walk(child)
            if found is not None:
                return found
        return None

    for child in node.children:
        found = walk(child)
        if found is not None:
            return found
    return None


def _is_nav_chrome_background_shell(child: CleanDesignTreeNode) -> bool:
    """Return True for full-bleed painted shells that are not nav destinations."""
    if find_nav_icon_node(child) is not None:
        return False
    if _node_has_nav_label(child):
        return False
    width = child.sizing.width
    if width is None or float(width) < NAV_SHELL_MIN_WIDTH:
        return False
    if child.type not in {NodeType.CONTAINER, NodeType.STACK}:
        return False
    style = child.style
    return bool(style.background_color or style.effects or style.elevation)


def _nav_tab_layout_left(child: CleanDesignTreeNode) -> float | None:
    """Resolve horizontal tab origin from stack placement or conserved layout rect."""
    placement = child.stack_placement
    if placement is not None and placement.left is not None:
        return float(placement.left)
    frame = child.geometry_frame
    if frame is not None and frame.layout_rect is not None and frame.layout_rect.x is not None:
        return float(frame.layout_rect.x)
    if child.offset_x:
        return float(child.offset_x)
    return None


def _nav_tab_layout_top(child: CleanDesignTreeNode) -> float:
    """Resolve vertical tab origin from stack placement or conserved layout rect."""
    placement = child.stack_placement
    if placement is not None and placement.top is not None:
        return float(placement.top)
    frame = child.geometry_frame
    if frame is not None and frame.layout_rect is not None and frame.layout_rect.y is not None:
        return float(frame.layout_rect.y)
    return float(child.offset_y or 0.0)


def _child_looks_like_icon_only_nav_tab(child: CleanDesignTreeNode) -> bool:
    """Return True for compact icon stacks used as bottom-nav tabs without labels."""
    if find_nav_icon_node(child) is None:
        return False
    width, height = _nav_tab_paint_extent(child)
    if width is None or height is None:
        return False
    if float(width) > COMPACT_ICON_NAV_TAB_MAX or float(height) > COMPACT_ICON_NAV_TAB_MAX:
        return False
    if child.stack_placement is None and _nav_tab_layout_left(child) is None:
        return False
    return child.type in {NodeType.STACK, NodeType.COLUMN, NodeType.CONTAINER}


def _conserved_node_paint_extent(node: CleanDesignTreeNode) -> tuple[float, float]:
    """Return paint width/height using sizing, placement, and conserved layout rect."""
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    frame = node.geometry_frame
    if frame is not None and frame.layout_rect is not None:
        rect = frame.layout_rect
        if rect.width is not None and float(rect.width) > 0:
            width = max(width, float(rect.width))
        if rect.height is not None and float(rect.height) > 0:
            height = max(height, float(rect.height))
    placement = node.stack_placement
    if placement is not None:
        if placement.width is not None and float(placement.width) > 0:
            width = max(width, float(placement.width))
        if placement.height is not None and float(placement.height) > 0:
            height = max(height, float(placement.height))
    return width, height


def _nav_tab_paint_extent(child: CleanDesignTreeNode) -> tuple[float | None, float | None]:
    """Return inclusive tab paint width/height from sizing and conserved layout rect."""
    width = child.sizing.width
    height = child.sizing.height
    frame = child.geometry_frame
    if frame is not None and frame.layout_rect is not None:
        rect = frame.layout_rect
        if rect.width is not None and float(rect.width) > 0:
            width = max(width or 0.0, float(rect.width))
        if rect.height is not None and float(rect.height) > 0:
            height = max(height or 0.0, float(rect.height))
    return width, height


def _variant_property_suffix_is_on(node: CleanDesignTreeNode) -> bool:
    """Return True when a component variant property value ends with an ``-On`` suffix."""
    if node.variant is None:
        return False
    for value in node.variant.variant_properties.values():
        token = value.strip().lower().replace("_", "-")
        if token.endswith("-on"):
            return True
    return False


def _nav_tab_has_prominent_paint_surface(tab: CleanDesignTreeNode) -> bool:
    """Return True when a tab hosts a painted surface larger than its icon slot."""
    tab_width, tab_height = _nav_tab_paint_extent(tab)
    base_width = float(tab_width or 0.0)
    base_height = float(tab_height or 0.0)
    for descendant in _walk_nav_descendants(tab, max_depth=4):
        if descendant.type != NodeType.CONTAINER:
            continue
        if not descendant.style.background_color:
            continue
        surface_width, surface_height = _conserved_node_paint_extent(descendant)
        if surface_width > base_width * 1.05 or surface_height > base_height * 1.05:
            return True
    return False


def _nav_tab_glyph_extent(tab: CleanDesignTreeNode) -> tuple[float, float]:
    """Return drawable glyph width/height for a bottom-nav icon tab."""
    icon_node = find_nav_icon_node(tab)
    if icon_node is not None:
        glyph_width = icon_node.sizing.width
        glyph_height = icon_node.sizing.height
        if (
            glyph_width is not None
            and glyph_height is not None
            and float(glyph_width) > 0
            and float(glyph_height) > 0
        ):
            return float(glyph_width), float(glyph_height)
    paint_width, paint_height = _nav_tab_paint_extent(tab)
    return float(paint_width or 24.0), float(paint_height or 24.0)


def _nav_tab_slot_extent(tab: CleanDesignTreeNode) -> tuple[float, float]:
    """Return interactive slot width/height, expanding to painted active surfaces."""
    from figma_flutter_agent.parser.numeric_rounding import round_geometry

    paint_width, paint_height = _nav_tab_paint_extent(tab)
    slot_width = float(paint_width or 0.0)
    slot_height = float(paint_height or 0.0)
    for descendant in _walk_nav_descendants(tab, max_depth=4):
        if descendant.type != NodeType.CONTAINER:
            continue
        if not descendant.style.background_color:
            continue
        surface_width, surface_height = _conserved_node_paint_extent(descendant)
        slot_width = max(slot_width, surface_width)
        slot_height = max(slot_height, surface_height)
    slot_width = max(slot_width, 44.0)
    slot_height = max(slot_height, 44.0)
    return round_geometry(slot_width), round_geometry(slot_height)


def _resolve_nav_active_tab(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Resolve the painted active tab from variant suffixes and checked metadata."""
    items = collect_bottom_nav_items(node)
    if not items:
        return None
    painted_on_tabs = [
        tab
        for tab in items
        if _variant_property_suffix_is_on(tab) and _nav_tab_has_prominent_paint_surface(tab)
    ]
    if len(painted_on_tabs) == 1:
        return painted_on_tabs[0]
    current_index = bottom_nav_current_index(node)
    return items[min(current_index, len(items) - 1)]


def _nav_tab_sort_key(child: CleanDesignTreeNode) -> tuple[float, float, str]:
    placement = child.stack_placement
    left = _nav_tab_layout_left(child)
    if left is not None:
        primary = left
    elif placement is not None and placement.right is not None:
        primary = 10000.0 - float(placement.right)
    else:
        primary = 0.0
    return (primary, _nav_tab_layout_top(child), child.id)


def _child_looks_like_pill_nav_tab(child: CleanDesignTreeNode) -> bool:
    """Return True for labeled pill stacks used as bottom-nav tabs (icon + text)."""
    if child.type not in {NodeType.STACK, NodeType.COLUMN}:
        return False
    width = child.sizing.width
    height = child.sizing.height
    if width is None or height is None:
        return False
    w = float(width)
    h = float(height)
    if not (
        PILL_NAV_MIN_WIDTH <= w <= PILL_NAV_MAX_WIDTH
        and PILL_NAV_MIN_HEIGHT <= h <= PILL_NAV_MAX_HEIGHT
    ):
        return False
    if child.stack_placement is None:
        return False
    if not _node_has_nav_label(child):
        return False
    return find_nav_icon_node(child) is not None


def _collect_pill_nav_tabs(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    tabs = [
        child
        for child in node.children
        if _child_looks_like_pill_nav_tab(child) and not _is_nav_chrome_background_shell(child)
    ]
    if tabs:
        return sorted(tabs, key=_nav_tab_sort_key)
    return []


def layout_fact_stack_pill_nav_tab(node: CleanDesignTreeNode) -> bool:
    """Return True for a STACK pill tab host (labeled compact nav destination)."""
    return _child_looks_like_pill_nav_tab(node)


def _collect_loose_icon_nav_tabs(
    node: CleanDesignTreeNode,
    *,
    exclude_ids: frozenset[str] = frozenset(),
) -> list[CleanDesignTreeNode]:
    """Return compact icon tabs even when fewer than two (for pill+icon mixes)."""
    tabs = [
        child
        for child in node.children
        if child.id not in exclude_ids
        and _child_looks_like_icon_only_nav_tab(child)
        and not _is_nav_chrome_background_shell(child)
    ]
    return sorted(tabs, key=_nav_tab_sort_key)


def _collect_icon_only_nav_tabs(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    tabs = [
        child
        for child in node.children
        if _child_looks_like_icon_only_nav_tab(child) and not _is_nav_chrome_background_shell(child)
    ]
    if len(tabs) >= 2:
        return sorted(tabs, key=_nav_tab_sort_key)
    return []


def _host_is_oversized_nav_collector(node: CleanDesignTreeNode) -> bool:
    """Return True when a node is too large to collect flat screen copy as nav tabs."""
    height = node.sizing.height
    width = node.sizing.width
    if height is not None and float(height) > MAX_BOTTOM_NAV_HOST_HEIGHT:
        return True
    if (
        width is not None
        and height is not None
        and float(width) > 0.0
        and float(height) / float(width) > 0.45
    ):
        return True
    return len(node.children) > 12


def _nested_bottom_nav_has_compact_anatomy(node: CleanDesignTreeNode) -> bool:
    """Return True for compact docked bottom-nav hosts with a bounded destination row."""
    height = node.sizing.height
    width = node.sizing.width
    if height is None or width is None or float(height) <= 0.0 or float(width) <= 0.0:
        return False
    if float(height) > MAX_BOTTOM_NAV_HOST_HEIGHT:
        return False
    if float(height) / float(width) > 0.45:
        return False
    destinations = [
        child
        for child in node.children
        if child.type in {NodeType.STACK, NodeType.COLUMN, NodeType.ROW, NodeType.CONTAINER}
    ]
    return MIN_BOTTOM_NAV_ITEMS <= len(destinations) <= MAX_BOTTOM_NAV_ITEMS


def _find_canonical_nested_bottom_nav(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Prefer a compact nested bottom-nav component inside an oversized host."""
    if not _host_is_oversized_nav_collector(node):
        return None

    def walk(candidate: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if candidate.type == NodeType.BOTTOM_NAV and _nested_bottom_nav_has_compact_anatomy(
            candidate
        ):
            return candidate
        for child in candidate.children:
            found = walk(child)
            if found is not None:
                return found
        return None

    return walk(node)


def _node_has_nav_label(node: CleanDesignTreeNode) -> bool:
    if node.text and node.text.strip():
        return True
    return any(
        descendant.type == NodeType.TEXT and descendant.text and descendant.text.strip()
        for descendant in _walk_nav_descendants(node, max_depth=6)
    )


def _walk_nav_descendants(
    node: CleanDesignTreeNode, *, max_depth: int, depth: int = 0
) -> list[CleanDesignTreeNode]:
    if depth > max_depth:
        return []
    found: list[CleanDesignTreeNode] = []
    for child in node.children:
        found.append(child)
        found.extend(_walk_nav_descendants(child, max_depth=max_depth, depth=depth + 1))
    return found


def _child_looks_like_nav_item(
    child: CleanDesignTreeNode,
    *,
    host: CleanDesignTreeNode,
) -> bool:
    if find_nav_icon_node(child) is not None:
        return True
    if not _node_has_nav_label(child):
        return False
    oversized = _host_is_oversized_nav_collector(host)
    if oversized and child.type == NodeType.TEXT:
        return False
    if oversized and child.type == NodeType.COLUMN and find_nav_icon_node(child) is None:
        width = child.sizing.width
        if width is not None and float(width) > 80.0:
            return False
    if child.type == NodeType.TEXT:
        return not oversized
    name = child.name.lower().strip()
    if name and name not in _NAV_ITEM_GENERIC_NAMES:
        return child.type in {NodeType.COLUMN, NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}
    return child.type in {NodeType.COLUMN, NodeType.ROW, NodeType.STACK}


def _collect_nav_item_rows(node: CleanDesignTreeNode) -> list[list[CleanDesignTreeNode]]:
    rows: list[list[CleanDesignTreeNode]] = []
    if node.type == NodeType.ROW and len(node.children) >= 2:
        nav_like = [
            child for child in node.children if _child_looks_like_nav_item(child, host=node)
        ]
        if len(nav_like) >= 2:
            rows.append(nav_like)
    for child in node.children:
        rows.extend(_collect_nav_item_rows(child))
    return rows


def bottom_nav_host_uses_icon_only_tabs(node: CleanDesignTreeNode) -> bool:
    """Return True when every resolved tab is a compact icon destination without labels."""
    items = collect_bottom_nav_items(node)
    if len(items) < MIN_BOTTOM_NAV_ITEMS:
        return False
    return all(_child_looks_like_icon_only_nav_tab(item) for item in items)


def collect_bottom_nav_items(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Resolve leaf bottom-nav tab items from direct or wrapped ROW containers."""
    nested = _find_canonical_nested_bottom_nav(node)
    if nested is not None:
        nested_items = _collect_bottom_nav_items_from_host(nested)
        if MIN_BOTTOM_NAV_ITEMS <= len(nested_items) <= MAX_BOTTOM_NAV_ITEMS:
            return nested_items
    return _collect_bottom_nav_items_from_host(node)


def _collect_bottom_nav_items_from_host(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    if not node.children:
        return []
    direct = [child for child in node.children if _child_looks_like_nav_item(child, host=node)]
    if MIN_BOTTOM_NAV_ITEMS <= len(direct) <= MAX_BOTTOM_NAV_ITEMS:
        return direct
    rows = _collect_nav_item_rows(node)
    if rows:
        best = max(rows, key=len)
        if MIN_BOTTOM_NAV_ITEMS <= len(best) <= MAX_BOTTOM_NAV_ITEMS:
            return best
    if len(node.children) == 1:
        inner = collect_bottom_nav_items(node.children[0])
        if inner:
            return inner
    icon_tabs = _collect_icon_only_nav_tabs(node)
    pill_tabs = _collect_pill_nav_tabs(node)
    if pill_tabs and icon_tabs:
        merged = sorted(pill_tabs + icon_tabs, key=_nav_tab_sort_key)
        if len(merged) <= MAX_BOTTOM_NAV_ITEMS:
            return merged
    if pill_tabs:
        loose_icons = _collect_loose_icon_nav_tabs(
            node,
            exclude_ids=frozenset(tab.id for tab in pill_tabs),
        )
        if loose_icons:
            merged = sorted(pill_tabs + loose_icons, key=_nav_tab_sort_key)
            if len(merged) <= MAX_BOTTOM_NAV_ITEMS:
                return merged
    if pill_tabs and MIN_BOTTOM_NAV_ITEMS <= len(pill_tabs) <= MAX_BOTTOM_NAV_ITEMS:
        return pill_tabs
    if icon_tabs and len(icon_tabs) <= MAX_BOTTOM_NAV_ITEMS:
        return icon_tabs
    if pill_tabs and len(pill_tabs) <= MAX_BOTTOM_NAV_ITEMS:
        return pill_tabs
    return []


def find_nav_icon_node(child: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the first descendant that carries a vector asset for a nav icon."""
    if child.vector_asset_key or child.image_asset_key:
        if child.type in {
            NodeType.IMAGE,
            NodeType.VECTOR,
            NodeType.STACK,
            NodeType.CONTAINER,
        }:
            return child
    for descendant in child.children:
        found = find_nav_icon_node(descendant)
        if found is not None:
            return found
    return None


def nav_icon_expr(
    child: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    project_dir: Path | None = None,
) -> str:
    """Build icon widget expression for a bottom-nav item from extracted Figma assets."""
    _ = project_dir
    icon_node = find_nav_icon_node(child)
    if icon_node is not None:
        if icon_node.image_asset_key:
            asset = escape_dart_string(icon_node.image_asset_key)
            return f"Image.asset('{asset}', width: 22, height: 22, fit: BoxFit.contain)"
        if icon_node.vector_asset_key and uses_svg:
            asset = escape_dart_string(icon_node.vector_asset_key)
            return f"SvgPicture.asset('{asset}', width: 22, height: 22)"
    return _NAV_ICON_FALLBACK


def layout_fact_column_nav_tab_label_host(node: CleanDesignTreeNode) -> bool:
    """Return True for the short label column nested inside a bottom-nav tab."""
    if node.type != NodeType.COLUMN:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (30.0 <= float(width) <= 56.0 and 14.0 <= float(height) <= 20.0):
        return False
    return not (len(node.children) != 1 or node.children[0].type != NodeType.TEXT)


def row_hosts_compact_nav_tabs(row: CleanDesignTreeNode) -> bool:
    """Return True when every child of a ``Row`` is a compact bottom-nav tab."""
    if row.type != NodeType.ROW or len(row.children) < 2:
        return False
    return all(layout_fact_column_compact_nav_tab(child) for child in row.children)


def _nav_tab_label_is_active(tab: CleanDesignTreeNode) -> bool:
    """Return True when tab copy uses an active (green) label tone."""
    for descendant in _walk_nav_descendants(tab, max_depth=4):
        if descendant.type != NodeType.TEXT:
            continue
        color = (descendant.style.text_color or "").lower()
        if not color:
            continue
        if color in {"0xff166534", "0xff2e7d32", "0xff15803d"}:
            return True
    return False


def _nav_color_is_near_white(color: str | None) -> bool:
    """Return True when a Figma color token is visually white."""
    if not color:
        return False
    normalized = color.lower().removeprefix("0x").removeprefix("#")
    if len(normalized) == 8:
        normalized = normalized[2:]
    try:
        value = int(normalized, 16)
    except ValueError:
        return False
    r = (value >> 16) & 0xFF
    g = (value >> 8) & 0xFF
    b = value & 0xFF
    return r >= 240 and g >= 240 and b >= 240


def _nav_tab_painted_fill(tab: CleanDesignTreeNode) -> str | None:
    """Return the first painted fill on a nav tab host or shallow descendants."""
    if tab.style.background_color:
        return tab.style.background_color
    for descendant in _walk_nav_descendants(tab, max_depth=4):
        if descendant.style.background_color:
            return descendant.style.background_color
    return None


def _nav_tab_label_text_color(tab: CleanDesignTreeNode) -> str | None:
    """Return the first label text color on a nav tab."""
    for descendant in _walk_nav_descendants(tab, max_depth=4):
        if descendant.type != NodeType.TEXT:
            continue
        if descendant.style.text_color:
            return descendant.style.text_color
    return None


def _nav_tab_icon_glyph_color(tab: CleanDesignTreeNode) -> str | None:
    """Return stroke/border color from the nav tab icon glyph when present."""
    icon_node = find_nav_icon_node(tab)
    if icon_node is None:
        return None
    for descendant in _walk_nav_descendants(icon_node, max_depth=4):
        if descendant.style.border_color:
            return descendant.style.border_color
        if descendant.style.text_color and not _nav_color_is_near_white(
            descendant.style.text_color
        ):
            return descendant.style.text_color
    if icon_node.style.border_color:
        return icon_node.style.border_color
    return None


def compact_nav_tab_should_paint_background(
    tab: CleanDesignTreeNode,
    *,
    parent_row: CleanDesignTreeNode | None,
) -> bool:
    """Return True when a compact nav tab should keep its painted highlight fill."""
    if not tab.style.background_color:
        return False
    if variant_is_checked(tab):
        return True
    if parent_row is None or not row_hosts_compact_nav_tabs(parent_row):
        return True
    highlighted = [
        child
        for child in parent_row.children
        if layout_fact_column_compact_nav_tab(child) and child.style.background_color
    ]
    if len(highlighted) <= 1:
        return True
    active_tabs = [child for child in highlighted if _nav_tab_label_is_active(child)]
    if active_tabs:
        return tab in active_tabs
    return False


def layout_fact_column_compact_nav_tab(node: CleanDesignTreeNode) -> bool:
    """Return True for a bottom-nav tab column that must scale inside a tight slot."""
    if node.type != NodeType.COLUMN:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (30.0 <= float(width) <= 96.0 and 40.0 <= float(height) <= 56.0):
        return False
    return _node_has_nav_label(node)


def layout_fact_stack_bottom_nav_active_tab_pill(node: CleanDesignTreeNode) -> bool:
    """Active bottom-nav tab with a painted pill surface and separate icon+label slots."""
    from figma_flutter_agent.parser.interaction import primary_surface_node

    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (40.0 <= float(width) <= 56.0 and 58.0 <= float(height) <= 72.0):
        return False
    if not _node_has_nav_label(node):
        return False
    surface = primary_surface_node(node)
    if surface is None:
        return False
    surface_width = float(surface.sizing.width or 0.0)
    surface_height = float(surface.sizing.height or 0.0)
    if surface_width <= 0.0 or surface_height <= 0.0:
        return False
    stack_area = float(width) * float(height)
    surface_area = surface_width * surface_height
    if stack_area <= 0.0 or surface_area / stack_area > 0.85:
        return False
    return surface_height < float(height) * 0.85


def layout_fact_stack_bottom_nav_tab_glyph_column(node: CleanDesignTreeNode) -> bool:
    """Compact bottom-nav tab stacks that flow icon + label in a tight slot."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (34.0 <= float(width) <= 80.0 and 40.0 <= float(height) <= 70.0):
        return False
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_is_absolute_overlay,
    )

    if any(stack_child_is_absolute_overlay(child) for child in node.children):
        return False
    return _node_has_nav_label(node)


def layout_fact_stack_bottom_nav_icon_tab_slot(node: CleanDesignTreeNode) -> bool:
    """Compact bottom-nav icon tabs that must keep square icon bounds (no circular clip)."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (34.0 <= float(width) <= 80.0 and 40.0 <= float(height) <= 70.0):
        return False
    return find_nav_icon_node(node) is not None


def bottom_nav_current_index(node: CleanDesignTreeNode) -> int:
    """Resolve selected tab index from child variants or nav-level metadata."""
    items = collect_bottom_nav_items(node)
    for index, child in enumerate(items):
        if variant_is_checked(child):
            return index
    painted_on_indices = [
        index
        for index, child in enumerate(items)
        if _variant_property_suffix_is_on(child) and _nav_tab_has_prominent_paint_surface(child)
    ]
    if len(painted_on_indices) == 1:
        return painted_on_indices[0]
    active_indices = [index for index, child in enumerate(items) if _nav_tab_label_is_active(child)]
    if len(active_indices) == 1:
        return active_indices[0]
    selected = get_variant_property(node, "selected", "selectedIndex", "activeIndex")
    if selected is not None and selected.strip().isdigit():
        return int(selected.strip())
    return 0


def nav_icon_asset_path(
    child: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    project_dir: Path | None = None,
) -> str | None:
    """Resolve a bundled SVG asset path for a bottom-nav tab icon."""
    _ = project_dir
    if not uses_svg:
        return None
    icon_node = find_nav_icon_node(child)
    if icon_node is not None and icon_node.vector_asset_key:
        return icon_node.vector_asset_key
    return None


def nav_icon_tab_spec_expr(child: CleanDesignTreeNode, *, uses_svg: bool) -> str:
    """Build a Dart ``_IconNavTabSpec`` expression from Figma tab geometry."""
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    asset = nav_icon_asset_path(child, uses_svg=uses_svg) or ""
    asset_lit = escape_dart_string(asset)
    slot_width, slot_height = _nav_tab_slot_extent(child)
    icon_width, icon_height = _nav_tab_glyph_extent(child)
    return (
        "_IconNavTabSpec("
        f"iconAsset: '{asset_lit}', "
        f"slotWidth: {format_geometry_literal(slot_width)}, "
        f"slotHeight: {format_geometry_literal(slot_height)}, "
        f"rowBandHeight: {format_geometry_literal(icon_height)}, "
        f"iconWidth: {format_geometry_literal(icon_width)}, "
        f"iconHeight: {format_geometry_literal(icon_height)}"
        ")"
    )


def nav_pill_palette(node: CleanDesignTreeNode) -> dict[str, str | float]:
    """Extract pill-nav colors and radius from painted Figma tab metadata."""
    from figma_flutter_agent.generator.layout.style import dart_color_expr
    from figma_flutter_agent.schemas import NodeStyle

    active_bg = "Theme.of(context).colorScheme.primaryContainer"
    active_fg = "Theme.of(context).colorScheme.onPrimaryContainer"
    inactive_fg = "Theme.of(context).colorScheme.onSurfaceVariant"
    pill_radius = 8.0
    items = collect_bottom_nav_items(node)
    current_index = bottom_nav_current_index(node)
    for tab in items:
        if tab.style.border_radius is not None and float(tab.style.border_radius) > 0:
            pill_radius = float(tab.style.border_radius)
    active_tab = _resolve_nav_active_tab(node)
    if active_tab is not None:
        painted_fill = _nav_tab_painted_fill(active_tab)
        if painted_fill:
            active_bg = dart_color_expr(
                NodeStyle(background_color=painted_fill),
                fallback=active_bg,
            )
        label_color = _nav_tab_label_text_color(active_tab)
        if label_color:
            active_fg = dart_color_expr(
                NodeStyle(text_color=label_color),
                css_key="color",
                fallback=active_fg,
            )
        for descendant in _walk_nav_descendants(active_tab, max_depth=4):
            if descendant.type != NodeType.CONTAINER:
                continue
            if not descendant.style.background_color:
                continue
            if (
                descendant.style.border_radius is not None
                and float(descendant.style.border_radius) > 0
            ):
                pill_radius = float(descendant.style.border_radius)
                break
    for index, tab in enumerate(items):
        if index == current_index:
            continue
        icon_color = _nav_tab_icon_glyph_color(tab)
        if icon_color and not _nav_color_is_near_white(icon_color):
            inactive_fg = dart_color_expr(
                NodeStyle(background_color=icon_color),
                fallback=inactive_fg,
            )
            break
        label_color = _nav_tab_label_text_color(tab)
        if label_color and not _nav_color_is_near_white(label_color):
            inactive_fg = dart_color_expr(
                NodeStyle(text_color=label_color),
                css_key="color",
                fallback=inactive_fg,
            )
            break
    return {
        "active_bg": active_bg,
        "active_fg": active_fg,
        "inactive_fg": inactive_fg,
        "pill_radius": pill_radius,
    }
