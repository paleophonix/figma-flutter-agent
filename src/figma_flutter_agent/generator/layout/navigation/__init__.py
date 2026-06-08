"""Navigation layout renderers."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.navigation.bottom import (
    render_bottom_navigation,
    render_pill_bottom_navigation,
)
from figma_flutter_agent.generator.layout.navigation.chrome import (
    bottom_nav_has_compact_pill_tabs,
    bottom_nav_has_figma_chrome,
    bottom_nav_stateful_helpers,
    compose_bottom_navigation_host,
    ensure_layout_chrome_nav_helpers,
    pill_nav_stateful_helpers,
    wrap_bottom_nav_figma_chrome,
)
from figma_flutter_agent.generator.layout.navigation.items import (
    bottom_nav_current_index,
    collect_bottom_nav_items,
    column_is_compact_nav_tab,
    column_is_nav_tab_label_host,
    compact_nav_tab_should_paint_background,
    find_nav_icon_node,
    nav_icon_expr,
    row_hosts_compact_nav_tabs,
)
from figma_flutter_agent.generator.layout.navigation.labels import (
    first_descendant_text_label,
    label_from_child,
    tab_label_from_child,
)
from figma_flutter_agent.generator.layout.navigation.tabs import (
    carousel_aspect_ratio_expr,
    render_carousel,
    render_tabs,
)
from figma_flutter_agent.generator.layout.navigation.tree import (
    first_node_id_of_type,
    tree_contains_node_type,
)

__all__ = [
    "bottom_nav_current_index",
    "bottom_nav_has_compact_pill_tabs",
    "bottom_nav_has_figma_chrome",
    "bottom_nav_stateful_helpers",
    "carousel_aspect_ratio_expr",
    "collect_bottom_nav_items",
    "column_is_compact_nav_tab",
    "column_is_nav_tab_label_host",
    "compact_nav_tab_should_paint_background",
    "row_hosts_compact_nav_tabs",
    "compose_bottom_navigation_host",
    "ensure_layout_chrome_nav_helpers",
    "pill_nav_stateful_helpers",
    "wrap_bottom_nav_figma_chrome",
    "find_nav_icon_node",
    "first_descendant_text_label",
    "first_node_id_of_type",
    "label_from_child",
    "nav_icon_expr",
    "render_bottom_navigation",
    "render_pill_bottom_navigation",
    "render_carousel",
    "render_tabs",
    "tab_label_from_child",
    "tree_contains_node_type",
]
