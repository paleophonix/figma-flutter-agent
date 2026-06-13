"""Bottom navigation item and icon resolution."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.navigation.labels import first_descendant_text_label
from figma_flutter_agent.generator.variant.state import (
    get_variant_property,
    variant_is_checked,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_NAV_SVG_ASSET_BY_NAME: tuple[tuple[tuple[str, ...], str], ...] = (
    (("главная", "home"), "assets/icons/home.svg"),
    (("каталог", "catalog"), "assets/icons/catalog.svg"),
    (("корзина", "cart", "shop", "bag"), "assets/icons/cart.svg"),
    (("профиль", "profile", "account", "user"), "assets/icons/profile.svg"),
)

_NAV_ICON_BY_NAME: tuple[tuple[tuple[str, ...], str], ...] = (
    (("главная", "home"), "Icons.home_outlined"),
    (("каталог", "catalog"), "Icons.grid_view_outlined"),
    (("search", "explore"), "Icons.search"),
    (("корзина", "cart", "shop", "bag"), "Icons.shopping_bag_outlined"),
    (("профиль", "profile", "account", "user"), "Icons.person_outline"),
    (("чаты", "chat", "message", "support"), "Icons.chat_bubble_outline"),
    (("адреса", "address", "location", "delivery"), "Icons.location_on_outlined"),
    (("карт", "card", "payment"), "Icons.credit_card_outlined"),
    (("уведомлен", "notif", "bell"), "Icons.notifications_outlined"),
    (("история", "заказ", "order", "history"), "Icons.history_outlined"),
    (("контакт", "support", "help"), "Icons.support_agent_outlined"),
    (("settings", "gear"), "Icons.settings_outlined"),
    (("favorite", "heart"), "Icons.favorite_border"),
)
_NAV_ITEM_GENERIC_NAMES = frozenset(
    {"link", "tab", "item", "nav", "navitem", "container", "frame", "background"}
)


def _node_has_nav_label(node: CleanDesignTreeNode) -> bool:
    if node.text and node.text.strip():
        return True
    return any(
        descendant.type == NodeType.TEXT
        and descendant.text
        and descendant.text.strip()
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


def _child_looks_like_nav_item(child: CleanDesignTreeNode) -> bool:
    if not _node_has_nav_label(child):
        return False
    if find_nav_icon_node(child) is not None:
        return True
    name = child.name.lower().strip()
    if name and name not in _NAV_ITEM_GENERIC_NAMES:
        return True
    return child.type in {NodeType.COLUMN, NodeType.ROW, NodeType.STACK, NodeType.TEXT}


def _collect_nav_item_rows(node: CleanDesignTreeNode) -> list[list[CleanDesignTreeNode]]:
    rows: list[list[CleanDesignTreeNode]] = []
    if node.type == NodeType.ROW and len(node.children) >= 2:
        nav_like = [child for child in node.children if _child_looks_like_nav_item(child)]
        if len(nav_like) >= 2:
            rows.append(nav_like)
    for child in node.children:
        rows.extend(_collect_nav_item_rows(child))
    return rows


def collect_bottom_nav_items(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Resolve leaf bottom-nav tab items from direct or wrapped ROW containers."""
    if not node.children:
        return []
    direct = [child for child in node.children if _child_looks_like_nav_item(child)]
    if len(direct) >= 2:
        return direct
    rows = _collect_nav_item_rows(node)
    if rows:
        return max(rows, key=len)
    if len(node.children) == 1:
        inner = collect_bottom_nav_items(node.children[0])
        if inner:
            return inner
    return list(node.children)


def find_nav_icon_node(child: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the first descendant that carries a vector asset for a nav icon."""
    if child.vector_asset_key and child.type in {NodeType.IMAGE, NodeType.VECTOR}:
        return child
    for descendant in child.children:
        found = find_nav_icon_node(descendant)
        if found is not None:
            return found
    return None


def nav_icon_expr(child: CleanDesignTreeNode, *, uses_svg: bool) -> str:
    """Build icon widget expression for a bottom-nav item."""
    label = first_descendant_text_label(child) or child.name
    name_lower = label.lower()
    if uses_svg:
        for tokens, asset_path in _NAV_SVG_ASSET_BY_NAME:
            if any(token in name_lower for token in tokens):
                asset = escape_dart_string(asset_path)
                return f"SvgPicture.asset('{asset}', width: 22, height: 22)"
    icon_node = find_nav_icon_node(child)
    if icon_node is not None and icon_node.vector_asset_key and uses_svg:
        asset = escape_dart_string(icon_node.vector_asset_key)
        return f"SvgPicture.asset('{asset}', width: 22, height: 22)"
    for tokens, icon_name in _NAV_ICON_BY_NAME:
        if any(token in name_lower for token in tokens):
            return f"const Icon({icon_name})"
    return "const Icon(Icons.circle_outlined)"


def column_is_nav_tab_label_host(node: CleanDesignTreeNode) -> bool:
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
    return all(column_is_compact_nav_tab(child) for child in row.children)


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
        if column_is_compact_nav_tab(child) and child.style.background_color
    ]
    if len(highlighted) <= 1:
        return True
    active_tabs = [child for child in highlighted if _nav_tab_label_is_active(child)]
    if active_tabs:
        return tab in active_tabs
    return False


def column_is_compact_nav_tab(node: CleanDesignTreeNode) -> bool:
    """Return True for a bottom-nav tab column that must scale inside a tight slot."""
    if node.type != NodeType.COLUMN:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (60.0 <= float(width) <= 96.0 and 40.0 <= float(height) <= 56.0):
        return False
    return _node_has_nav_label(node)


def bottom_nav_current_index(node: CleanDesignTreeNode) -> int:
    """Resolve selected tab index from child variants or nav-level metadata."""
    items = collect_bottom_nav_items(node)
    for index, child in enumerate(items):
        if variant_is_checked(child):
            return index
    active_indices = [
        index for index, child in enumerate(items) if _nav_tab_label_is_active(child)
    ]
    if len(active_indices) == 1:
        return active_indices[0]
    selected = get_variant_property(node, "selected", "selectedIndex", "activeIndex")
    if selected is not None and selected.strip().isdigit():
        return int(selected.strip())
    return 0


def nav_icon_asset_path(child: CleanDesignTreeNode, *, uses_svg: bool) -> str | None:
    """Resolve a bundled SVG asset path for a bottom-nav tab icon."""
    if not uses_svg:
        return None
    label = first_descendant_text_label(child) or child.name
    name_lower = label.lower()
    for tokens, asset_path in _NAV_SVG_ASSET_BY_NAME:
        if any(token in name_lower for token in tokens):
            return asset_path
    icon_node = find_nav_icon_node(child)
    if icon_node is not None and icon_node.vector_asset_key:
        return icon_node.vector_asset_key
    return None


def nav_pill_palette(node: CleanDesignTreeNode) -> dict[str, str | float]:
    """Extract pill-nav colors and radius from painted Figma tab metadata."""
    active_bg = "0xFFDCFCE7"
    active_fg = "0xFF166534"
    inactive_fg = "0xFF64748B"
    pill_radius = 8.0
    items = collect_bottom_nav_items(node)
    for tab in items:
        if tab.style.border_radius is not None and float(tab.style.border_radius) > 0:
            pill_radius = float(tab.style.border_radius)
        if tab.style.background_color:
            active_bg = tab.style.background_color
    for tab in items:
        if not _nav_tab_label_is_active(tab):
            continue
        for descendant in _walk_nav_descendants(tab, max_depth=4):
            if descendant.type != NodeType.TEXT:
                continue
            if descendant.style.text_color:
                active_fg = descendant.style.text_color
                break
    for tab in items:
        if _nav_tab_label_is_active(tab):
            continue
        for descendant in _walk_nav_descendants(tab, max_depth=4):
            if descendant.type != NodeType.TEXT:
                continue
            if descendant.style.text_color:
                inactive_fg = descendant.style.text_color
                break
    return {
        "active_bg": active_bg,
        "active_fg": active_fg,
        "inactive_fg": inactive_fg,
        "pill_radius": pill_radius,
    }
