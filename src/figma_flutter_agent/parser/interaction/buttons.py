"""Button and navigation affordance predicates."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.colors import fill_luminance, is_greenish_fill
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

from .icons import (
    _has_circular_container,
    _stack_has_vector_icon,
    looks_like_compact_icon_action_stack,
    looks_like_favorite_glyph_vector,
)
from .shared import (
    _ACTION_HINTS,
    _BACK_NAV_DESCENDANT_DEPTH,
    _MAX_LOCAL_DEPTH,
    _argb_color_key,
    _descendant_nodes,
    _local_nodes,
    _subtree_text_node_count,
)

_LIST_TILE_LEAD_MAX_WIDTH = 64.0
_LIST_TILE_TRAIL_MAX_WIDTH = 32.0
_METADATA_COLUMN_MAX_WIDTH = 140.0
_ROW_BODY_SEARCH_DEPTH = 8


def _is_structural_button_shell(child: CleanDesignTreeNode) -> bool:
    """Return True for inner layout stacks that only wrap one social-style button row."""
    if child.type != NodeType.STACK:
        return False
    local_nodes = _local_nodes(child, _MAX_LOCAL_DEPTH)
    has_surface = any(
        item.type == NodeType.CONTAINER and (item.style.background_color or item.style.border_color)
        for item in local_nodes
    )
    has_action_text = any(
        item.type == NodeType.TEXT
        and item.text
        and any(hint in item.text.lower() for hint in _ACTION_HINTS)
        for item in local_nodes
    )
    return has_surface and has_action_text


def looks_like_plus_icon_button(node: CleanDesignTreeNode) -> bool:
    """Green circular add-to-cart controls with a flattened plus glyph."""
    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (32.0 <= float(width) <= 48.0 and 32.0 <= float(height) <= 48.0):
        return False
    background = _argb_color_key(node.style.background_color)
    if not is_greenish_fill(background):
        return False
    local_nodes = _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)
    for item in local_nodes:
        if item.type != NodeType.VECTOR:
            continue
        glyph_w = item.sizing.width
        glyph_h = item.sizing.height
        if glyph_w is None or glyph_h is None:
            continue
        if not (10.0 <= float(glyph_w) <= 18.0 and 10.0 <= float(glyph_h) <= 18.0):
            continue
        if abs(float(glyph_w) - float(glyph_h)) > 2.0:
            continue
        glyph_color = _argb_color_key(item.style.background_color)
        glyph_luminance = fill_luminance(glyph_color)
        if glyph_luminance is not None and glyph_luminance > 0.75:
            return True
    return False


def looks_like_favorite_icon_button(node: CleanDesignTreeNode) -> bool:
    """Circular product-card wishlist buttons with a filled heart vector."""
    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (28.0 <= float(width) <= 40.0 and 28.0 <= float(height) <= 40.0):
        return False
    background = _argb_color_key(node.style.background_color)
    bg_luminance = fill_luminance(background)
    if bg_luminance is None or bg_luminance < 0.85:
        return False
    local_nodes = _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)
    return any(looks_like_favorite_glyph_vector(item) for item in local_nodes)


def looks_like_back_nav_stack(node: CleanDesignTreeNode) -> bool:
    """Circular or compact icon affordance (back, close, favorite, download)."""
    if looks_like_compact_icon_action_stack(node):
        return True
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (44.0 <= width <= 64.0 and 44.0 <= height <= 64.0):
        return False
    local_nodes = _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)
    return _has_circular_container(local_nodes) and _stack_has_vector_icon(local_nodes)


def is_back_navigation_icon_stack(node: CleanDesignTreeNode) -> bool:
    """Return True for back/close affordances (not favorite/download/share)."""
    if not looks_like_back_nav_stack(node) and not looks_like_compact_icon_action_stack(node):
        return False
    labels = [
        (node.name or "").lower(),
        (node.accessibility_label or "").lower(),
    ]
    if node.variant is not None and node.variant.component_name:
        labels.append(node.variant.component_name.lower())
    combined = " ".join(labels)
    if any(token in combined for token in ("heart", "favorite", "download", "share")):
        return False
    if looks_like_favorite_icon_button(node):
        return False
    if looks_like_compact_icon_action_stack(node):
        return True
    return any(
        token in combined
        for token in (
            "back",
            "close",
            "arrow-left",
            "arrow-narrow-left",
            "chevron-left",
            "x",
            "vector 13",
        )
    )


def looks_like_skip_control_stack(node: CleanDesignTreeNode) -> bool:
    """Small skip/rewind control with a numeric label (e.g. 15 seconds)."""
    if node.type != NodeType.STACK:
        return False
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_hosts_notification_badge_overlay,
    )

    from .enrichment import find_raster_photo_leaf

    if stack_hosts_notification_badge_overlay(node):
        return False
    if find_raster_photo_leaf(node) is not None:
        return False
    if node.image_asset_key:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (28.0 <= width <= 56.0 and 28.0 <= height <= 56.0):
        return False
    for text_node in _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH):
        if text_node.type != NodeType.TEXT or not text_node.text:
            continue
        label = text_node.text.strip()
        if label.isdigit() and len(label) <= 2:
            return True
    return bool(not node.children and node.cluster_id and _stack_has_vector_icon([node]))


def button_stack_has_left_icon(parent_node: CleanDesignTreeNode) -> bool:
    """True when a tap row has a brand/icon anchor in the left fifth of the button."""
    parent_width = parent_node.sizing.width
    if parent_width is None or parent_width <= 0:
        return False
    threshold = float(parent_width) * 0.22

    def _icon_on_left(node: CleanDesignTreeNode) -> bool:
        if node.type == NodeType.VECTOR and node.vector_asset_key:
            placement = node.stack_placement
            left = placement.left if placement is not None and placement.left is not None else 0.0
            return left < threshold
        return False

    for child in parent_node.children:
        if _icon_on_left(child):
            return True
        if child.type == NodeType.STACK and len(child.children) <= 4:
            if any(_icon_on_left(item) for item in child.children):
                return True
    return False


def looks_like_play_pause_control_stack(node: CleanDesignTreeNode) -> bool:
    """Center play/pause cluster (circle + pause bars)."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width < 70.0 or height < 70.0:
        return False
    if width > 150.0 or height > 150.0:
        return False
    if node.render_boundary and not node.children:
        if node.cluster_id:
            return False
        flattened = node.flatten_figma_node_ids or ()
        return len(flattened) >= 4
    local_nodes = _local_nodes(node, _MAX_LOCAL_DEPTH)
    bars = 0
    cores = 0
    for item in local_nodes:
        if item.type != NodeType.CONTAINER:
            continue
        w = item.sizing.width
        h = item.sizing.height
        if w is None or h is None:
            continue
        wf = float(w)
        hf = float(h)
        if hf > wf * 1.4 and hf >= 18.0:
            bars += 1
        if abs(wf - hf) <= 6.0 and wf >= 50.0:
            cores += 1
    return bars >= 2 and cores >= 1


def looks_like_media_controls_stack(node: CleanDesignTreeNode) -> bool:
    """Player chrome: play/pause, skip, and a ``MM:SS`` timeline row."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width < 280.0 or height < 120.0:
        return False
    local_nodes = _local_nodes(node, 5)
    has_timestamps = any(
        item.type == NodeType.TEXT
        and item.text
        and ":" in item.text
        and len(item.text.strip()) <= 8
        for item in local_nodes
    )
    has_play = looks_like_play_pause_control_stack(node) or any(
        looks_like_play_pause_control_stack(item)
        for item in local_nodes
        if item.type == NodeType.STACK
    )
    return has_timestamps and has_play


def button_has_list_tile_row_body(node: CleanDesignTreeNode) -> bool:
    """Return True when a tappable frame is a horizontal icon + text + chevron row.

    Args:
        node: Parsed clean-tree button host.

    Returns:
        ``True`` when the node uses auto-layout spacing with a growing text block
        between compact leading/trailing chrome.
    """
    from figma_flutter_agent.schemas import SizingMode

    if node.type != NodeType.BUTTON or len(node.children) < 2 or node.spacing <= 0:
        return False
    has_fill = any(child.sizing.width_mode == SizingMode.FILL for child in node.children)
    if not has_fill and len(node.children) < 3:
        return False
    lead_width = node.children[0].sizing.width
    trail_width = node.children[-1].sizing.width if len(node.children) >= 3 else None
    compact_lead = lead_width is not None and float(lead_width) <= _LIST_TILE_LEAD_MAX_WIDTH
    compact_trail = trail_width is not None and float(trail_width) <= _LIST_TILE_TRAIL_MAX_WIDTH
    text_lines = sum(_subtree_text_node_count(child) for child in node.children)
    return text_lines >= 2 and (compact_lead or compact_trail)


def button_has_composite_row_body(node: CleanDesignTreeNode) -> bool:
    """Return True when a tappable frame hosts a list-card style row body.

    These bodies pair a growing text column with a fixed-width metadata column
    (timestamp, badge). They must keep intrinsic vertical sizing in Flutter:
    the Figma bbox is often shorter than ``StrutStyle`` layout metrics.

    Args:
        node: Parsed clean-tree button/stack host.

    Returns:
        ``True`` when the subtree contains a multi-child ``Row`` with a narrow
        metadata sibling.
    """
    if node.type not in {NodeType.BUTTON, NodeType.STACK}:
        return False

    def walk(current: CleanDesignTreeNode, depth: int) -> bool:
        if depth > _ROW_BODY_SEARCH_DEPTH:
            return False
        if current.type == NodeType.ROW and len(current.children) >= 2:
            has_primary = any(
                child.type in {NodeType.COLUMN, NodeType.CONTAINER, NodeType.STACK}
                for child in current.children
            )
            has_metadata = any(
                child.sizing.width is not None
                and 0 < float(child.sizing.width) <= _METADATA_COLUMN_MAX_WIDTH
                for child in current.children
            )
            if has_primary and has_metadata:
                return True
        return any(walk(child, depth + 1) for child in current.children)

    return walk(node, 0)


def _button_vertical_auto_layout_stack(node: CleanDesignTreeNode) -> bool:
    """True when spaced button children exactly fill the host height in order."""
    from figma_flutter_agent.generator.layout.button_flow import (
        button_vertical_auto_layout_stack,
    )

    return button_vertical_auto_layout_stack(node)


_GEOMETRY_SOCIAL_ROW_CONFIDENCE = 0.65
_SOCIAL_AUTH_ICON_MAX_EXTENT = 64.0


def button_has_social_auth_icon_label_body(node: CleanDesignTreeNode) -> bool:
    """Return True when a button body is a compact icon beside a centered label.

    Promoted social-auth rows compile as ``NodeType.BUTTON`` hosts with a small
    leading glyph stack and a single label line. Those bodies must emit as a
    ``Row``, not an overlay ``Stack``.

    Args:
        node: Parsed clean-tree button host.

    Returns:
        ``True`` when geometry and child structure match a social auth row body.
    """
    from figma_flutter_agent.parser.geometry import auth_button_confidence

    if node.type != NodeType.BUTTON or len(node.children) < 2:
        return False
    if button_hosts_multiple_auth_rows(node):
        return False
    if auth_button_confidence(node) < 0.5:
        return False
    has_icon = False
    has_label = False
    for child in node.children:
        if child.type == NodeType.TEXT:
            has_label = True
            continue
        if child.type not in {NodeType.VECTOR, NodeType.STACK}:
            continue
        lead_width = child.sizing.width
        lead_height = child.sizing.height
        if lead_width is None or lead_height is None:
            continue
        if (
            float(lead_width) <= _SOCIAL_AUTH_ICON_MAX_EXTENT
            and float(lead_height) <= _SOCIAL_AUTH_ICON_MAX_EXTENT
        ):
            has_icon = True
    return has_icon and has_label


def button_hosts_multiple_auth_rows(node: CleanDesignTreeNode) -> bool:
    """Return True when a host stacks two or more independent social auth rows."""
    from figma_flutter_agent.parser.geometry import (
        auth_button_confidence,
        social_auth_row_confidence,
    )

    def is_auth_row(child: CleanDesignTreeNode) -> bool:
        return (
            social_auth_row_confidence(child) >= _GEOMETRY_SOCIAL_ROW_CONFIDENCE
            or auth_button_confidence(child) >= 0.5
        )

    def count_auth_rows(children: list[CleanDesignTreeNode]) -> int:
        return sum(1 for child in children if is_auth_row(child))

    if node.type not in {NodeType.BUTTON, NodeType.STACK, NodeType.COLUMN}:
        return False
    if count_auth_rows(node.children) >= 2:
        return True
    for child in node.children:
        if child.type not in {NodeType.COLUMN, NodeType.STACK, NodeType.BUTTON}:
            continue
        if count_auth_rows(child.children) >= 2:
            return True
    return False


def button_hosts_nested_interactive_buttons(node: CleanDesignTreeNode) -> bool:
    """Return True when descendant buttons own tap targets and the host must stay passive.

    Card-style hosts (order history, settings rows with trailing actions) are often
    classified as a single ``BUTTON`` in Figma while embedding real action buttons.
    The outer shell must compile as a decorative container — only inner buttons get
    ``InkWell`` / ``onTap`` handlers.

    Args:
        node: Parsed clean-tree button host.

    Returns:
        ``True`` when any descendant ``BUTTON`` exists below ``node``.
    """
    if node.type != NodeType.BUTTON:
        return False
    if button_hosts_multiple_auth_rows(node):
        return True
    return any(
        descendant.type == NodeType.BUTTON and descendant.id != node.id
        for descendant in _descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)
    )


def button_should_flow_as_column(node: CleanDesignTreeNode) -> bool:
    """Return True when a button hosts multiple vertically stacked flow panels.

    List-card tap targets often pair a metadata ``Row`` with a trailing action
    ``Row``. Those panels must compile as a ``Column`` — a ``Stack`` paints them
    on top of each other.

    Args:
        node: Parsed clean-tree button host.

    Returns:
        ``True`` when at least two direct flow children are vertically sequential.
    """
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        tree_children_are_vertically_sequential,
    )

    if node.type != NodeType.BUTTON or len(node.children) < 2:
        return False
    if button_hosts_multiple_auth_rows(node):
        return True
    if button_has_list_tile_row_body(node):
        return False
    panel_types = {
        NodeType.BUTTON,
        NodeType.ROW,
        NodeType.COLUMN,
        NodeType.STACK,
        NodeType.CONTAINER,
        NodeType.CARD,
    }
    panels = [child for child in node.children if child.type in panel_types]
    if len(panels) < 2:
        return False
    if tree_children_are_vertically_sequential(node.children):
        return True
    return _button_vertical_auto_layout_stack(node)


def host_prefers_intrinsic_extent(node: CleanDesignTreeNode) -> bool:
    """Return True when a button host must size vertically from content, not Figma cap."""
    if node.type != NodeType.BUTTON:
        return False
    return (
        button_should_flow_as_column(node)
        or button_hosts_stacked_text_column(node)
        or button_has_composite_row_body(node)
        or button_has_list_tile_row_body(node)
    )


def button_hosts_stacked_text_column(node: CleanDesignTreeNode) -> bool:
    """Return True when a button body is a spaced title/subtitle ``Column``.

    Figma often pins these hosts to a bbox that is fractionally shorter than
    ``StrutStyle`` text metrics once flex ``spacing`` is applied.

    Args:
        node: Parsed clean-tree button host.

    Returns:
        ``True`` when a direct child is a multi-child ``Column`` with spacing.
    """
    if node.type != NodeType.BUTTON:
        return False
    return any(
        child.type == NodeType.COLUMN and (child.spacing or 0.0) > 0.0 and len(child.children) >= 2
        for child in node.children
    )


def button_is_left_aligned_text_label(node: CleanDesignTreeNode) -> bool:
    """Return True when a button hosts a single growing left-aligned title line."""
    from figma_flutter_agent.generator.layout.flex_policy.buttons import (
        button_is_pill_with_centered_label,
    )

    if node.type != NodeType.BUTTON or len(node.children) != 1:
        return False
    if button_is_pill_with_centered_label(node):
        return False
    child = node.children[0]
    if child.type != NodeType.TEXT:
        return False
    align = (child.style.text_align or "LEFT").upper()
    if align != "LEFT":
        return False
    return child.sizing.width_mode == SizingMode.FILL


def button_is_square_cart_product_thumbnail(node: CleanDesignTreeNode) -> bool:
    """Square tap host whose children decompose a raster thumbnail and quantity scrim."""
    from .enrichment import find_raster_photo_leaf

    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) < 64.0 or float(height) < 64.0:
        return False
    if abs(float(width) - float(height)) > max(8.0, float(width) * 0.12):
        return False
    return find_raster_photo_leaf(node) is not None
