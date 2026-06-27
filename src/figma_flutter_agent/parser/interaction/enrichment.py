"""Tree enrichment and data extraction for interactive Figma nodes."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .product import layout_fact_cart_quantity_scrim_row
from .shared import _descendant_nodes


def extract_cart_quantity_digit(node: CleanDesignTreeNode) -> str | None:
    """Return a cart quantity digit from overlay descendants or preserved prune fields."""
    for item in _descendant_nodes(node, 3):
        if item.type != NodeType.TEXT:
            continue
        text = (item.text or "").strip()
        if text.isdigit() and 0 < len(text) <= 3:
            return text
    direct = (node.text or "").strip()
    if direct.isdigit() and 0 < len(direct) <= 3:
        return direct
    label = (node.accessibility_label or "").strip()
    if label.isdigit() and 0 < len(label) <= 3:
        return label
    return None


def layout_fact_cart_quantity_overlay(node: CleanDesignTreeNode) -> bool:
    """Square black scrim with a centered numeric quantity over a product photo."""
    return (
        layout_fact_cart_quantity_scrim_row(node) and extract_cart_quantity_digit(node) is not None
    )


def enrich_pruned_cart_quantity_overlays(
    root: CleanDesignTreeNode,
    *,
    text_by_figma_id: dict[str, str] | None = None,
) -> None:
    """Restore quantity digits on cluster-pruned cart scrim rows from flattened Figma ids."""
    if not text_by_figma_id:
        return

    def walk(node: CleanDesignTreeNode) -> None:
        if (
            layout_fact_cart_quantity_scrim_row(node)
            and extract_cart_quantity_digit(node) is None
            and node.flatten_figma_node_ids
        ):
            for figma_id in node.flatten_figma_node_ids:
                candidate = text_by_figma_id.get(figma_id, "").strip()
                if candidate.isdigit() and 0 < len(candidate) <= 3:
                    node.text = candidate
                    break
        for child in node.children:
            walk(child)

    walk(root)


def collect_figma_text_by_id(raw_node: dict[str, object]) -> dict[str, str]:
    """Index Figma ``TEXT`` node characters by node id for prune recovery."""
    index: dict[str, str] = {}

    def walk(node: dict[str, object]) -> None:
        node_id = node.get("id")
        if node.get("type") == "TEXT" and isinstance(node_id, str):
            characters = str(node.get("characters") or "").strip()
            if characters:
                index[node_id] = characters
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    walk(child)

    walk(raw_node)
    return index


def find_raster_photo_leaf(
    node: CleanDesignTreeNode,
    *,
    depth: int = 0,
) -> CleanDesignTreeNode | None:
    """Return the first raster photo leaf under a thumbnail or card hero host."""
    if depth > 6:
        return None
    if node.type == NodeType.IMAGE:
        return node
    if node.image_asset_key and _node_is_large_raster_photo_candidate(node):
        return node
    walk_types = {
        NodeType.STACK,
        NodeType.COLUMN,
        NodeType.CONTAINER,
        NodeType.ROW,
        NodeType.BUTTON,
        NodeType.IMAGE,
        NodeType.VECTOR,
    }
    if node.type in walk_types:
        for child in node.children:
            if layout_fact_cart_quantity_scrim_row(child):
                continue
            found = find_raster_photo_leaf(child, depth=depth + 1)
            if found is not None:
                return found
    return None


def _node_is_large_raster_photo_candidate(node: CleanDesignTreeNode) -> bool:
    """Return True when a node carries a raster export large enough for hero imagery."""
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return node.type == NodeType.IMAGE
    return float(width) >= 64.0 and float(height) >= 48.0


def skip_control_left_side_of_parent(
    node: CleanDesignTreeNode,
    *,
    parent_width: float | None = None,
) -> bool:
    """Infer rewind (left) vs forward (right) skip from absolute placement pins."""
    placement = node.stack_placement
    if placement is None:
        return False
    width = parent_width if parent_width is not None and parent_width > 0 else 374.0
    node_w = float(node.sizing.width or 0.0)
    threshold = float(width) * 0.35
    if placement.left is not None:
        return float(placement.left) < threshold
    if placement.right is not None:
        inferred_left = float(width) - float(placement.right) - node_w
        return inferred_left < threshold
    return False


def list_tile_leading_icon_slot(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
    *,
    parent_type: NodeType | None = None,
) -> bool:
    """Return True when ``node`` is the leading icon rail in a settings-style list row.

    Args:
        node: Candidate leading icon host.
        parent_node: Immediate parent clean-tree node.
        parent_type: Parent node type from the render pass.

    Returns:
        ``True`` for the first compact child of a list-tile ``Row`` body.
    """
    from figma_flutter_agent.schemas import SizingMode

    from .buttons import _LIST_TILE_LEAD_MAX_WIDTH, button_has_list_tile_row_body

    if parent_node is None:
        return False
    row_host = parent_node
    if parent_type == NodeType.BUTTON and button_has_list_tile_row_body(parent_node):
        row_host = parent_node
    elif parent_type != NodeType.ROW:
        return False
    if not row_host.children or row_host.children[0].id != node.id:
        return False
    if len(row_host.children) < 3:
        return False
    from figma_flutter_agent.generator.layout.flex_policy import (
        layout_fact_row_icon_stepper_control_row,
    )

    if layout_fact_row_icon_stepper_control_row(row_host):
        return False
    has_fill = any(child.sizing.width_mode == SizingMode.FILL for child in row_host.children)
    if not has_fill:
        return False
    lead_width = node.sizing.width
    return not (lead_width is not None and float(lead_width) > _LIST_TILE_LEAD_MAX_WIDTH)


def stack_interaction_kind(node: CleanDesignTreeNode) -> str | None:
    """Classify absolute ``STACK`` groups as tap targets or text fields.

    Args:
        node: Parsed clean-tree node (typically ``STACK`` from a Figma ``GROUP``).

    Returns:
        ``"input"``, ``"button"``, or ``None``.
    """
    from .buttons import (
        _is_structural_button_shell,
        button_hosts_multiple_auth_rows,
        layout_fact_skip_control_stack,
    )
    from .forms import (
        _looks_like_form_field_stack,
        _stack_spans_primary_button_and_footer_link,
        layout_fact_password_field_stack,
    )
    from .shared import (
        _INPUT_HINTS,
        _MAX_CONTROL_CHILDREN,
        _MAX_CONTROL_HEIGHT,
        _MAX_LOCAL_DEPTH,
        _label_matches_action_hint,
        _local_nodes,
    )

    if node.type != NodeType.STACK:
        return None

    from .product import (
        layout_fact_checkout_sticky_footer_host,
        layout_fact_stack_product_purchase_footer_panel,
    )

    if (
        layout_fact_stack_product_purchase_footer_panel(node)
        or layout_fact_checkout_sticky_footer_host(node)
    ):
        return None

    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_stack_circular_option_glyph_host,
    )

    if layout_fact_stack_circular_option_glyph_host(node):
        return None

    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_icon_badge_stack,
    )

    if layout_fact_icon_badge_stack(node):
        return None

    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_stack_bottom_nav_tab_glyph_column,
    )

    if layout_fact_stack_bottom_nav_tab_glyph_column(node):
        return None

    if button_hosts_multiple_auth_rows(node):
        return None

    if layout_fact_password_field_stack(node):
        return "input"

    if layout_fact_skip_control_stack(node):
        return "button"

    from .icons import layout_fact_stack_vertical_icon_label_chip_tile

    if layout_fact_stack_vertical_icon_label_chip_tile(node):
        return "button"

    height = node.sizing.height
    if height is not None and height > _MAX_CONTROL_HEIGHT:
        return None
    if len(node.children) > _MAX_CONTROL_CHILDREN:
        return None

    nested_kind = next(
        (
            kind
            for child in node.children
            if child.type == NodeType.STACK
            and not _is_structural_button_shell(child)
            and (kind := stack_interaction_kind(child)) is not None
        ),
        None,
    )
    if nested_kind is not None:
        return None

    local_nodes = _local_nodes(node, _MAX_LOCAL_DEPTH)
    text_nodes = [n for n in local_nodes if n.type == NodeType.TEXT and n.text]
    if not text_nodes:
        return None
    surfaces = [
        n
        for n in local_nodes
        if n.type == NodeType.CONTAINER
        and (
            n.style.background_color is not None
            or n.style.border_color is not None
            or n.style.border_radius is not None
        )
    ]
    if not surfaces:
        return None

    for text_node in text_nodes:
        label = (text_node.text or text_node.name or "").strip().lower()
        if any(hint in label for hint in _INPUT_HINTS) and len(label) < 48:
            return "input"

    for text_node in text_nodes:
        label = (text_node.text or text_node.name or "").strip().lower()
        if _label_matches_action_hint(label):
            if _stack_spans_primary_button_and_footer_link(node, text_nodes=text_nodes):
                return None
            return "button"

    if _looks_like_form_field_stack(text_nodes=text_nodes, surfaces=surfaces):
        return "input"

    return None
