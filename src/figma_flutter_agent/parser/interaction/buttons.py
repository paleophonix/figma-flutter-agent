"""Button and navigation affordance predicates."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

from .shared import (
    _ACTION_HINTS,
    _BACK_NAV_DESCENDANT_DEPTH,
    _MAX_LOCAL_DEPTH,
    _argb_color_key,
    _descendant_nodes,
    _label_matches_action_hint,
    _local_nodes,
    _subtree_text_node_count,
)
from .icons import (
    _has_circular_container,
    _has_icon_action_name,
    _stack_has_vector_icon,
    looks_like_compact_icon_action_stack,
    looks_like_favorite_glyph_vector,
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
        item.type == NodeType.CONTAINER
        and (item.style.background_color or item.style.border_color)
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
    if background not in {"0xFF28A745", "0xFF2E7D32"}:
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
        if glyph_color == "0xFFFFFFFF":
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
    if background != "0xFFFFFFFF":
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
    if not node.children and node.cluster_id and _stack_has_vector_icon([node]):
        return True
    return False


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
    compact_trail = (
        trail_width is not None and float(trail_width) <= _LIST_TILE_TRAIL_MAX_WIDTH
    )
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
        child.type == NodeType.COLUMN
        and (child.spacing or 0.0) > 0.0
        and len(child.children) >= 2
        for child in node.children
    )


def button_is_left_aligned_text_label(node: CleanDesignTreeNode) -> bool:
    """Return True when a button hosts a single growing left-aligned title line."""
    if node.type != NodeType.BUTTON or len(node.children) != 1:
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
