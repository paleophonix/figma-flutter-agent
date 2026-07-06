"""Selection affordances for payment and option cards."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.colors import is_greenish_fill
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_FLEX_LABEL_HOST_TYPES = frozenset({NodeType.ROW, NodeType.COLUMN, NodeType.CARD, NodeType.STACK})


def _column_hosts_compact_radio_header(column: CleanDesignTreeNode) -> bool:
    """Column with one radio glyph and one external label — not a card surface."""
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    if column.type != NodeType.COLUMN:
        return False
    radios: list[CleanDesignTreeNode] = []
    labels: list[CleanDesignTreeNode] = []
    for child in column.children:
        if child.type == NodeType.TEXT:
            labels.append(child)
            continue
        if child.type == NodeType.RADIO:
            radios.append(child)
            continue
        for item in _descendant_nodes(child, 3):
            if item.type == NodeType.RADIO:
                radios.append(item)
    if len(radios) != 1 or len(labels) != 1:
        return False
    return len(column.children) <= 3


def layout_fact_card_compact_radio_header(node: CleanDesignTreeNode) -> bool:
    """Radio group header row inside a card shell — emit inline row, not elevated Card."""
    if node.type != NodeType.CARD:
        return False
    if len(node.children) == 1 and _column_hosts_compact_radio_header(node.children[0]):
        return True
    radios = [child for child in node.children if child.type == NodeType.RADIO]
    labels = [child for child in node.children if child.type == NodeType.TEXT]
    if len(radios) != 1 or not labels:
        return False
    if len(node.children) > 3:
        return False
    return layout_fact_compact_radio_glyph(radios[0], node)


def layout_fact_compact_radio_label_row(node: CleanDesignTreeNode) -> bool:
    """Compact payment row: radio glyph beside a single-line label."""
    if node.type != NodeType.ROW:
        return False
    has_radio = any(child.type == NodeType.RADIO for child in node.children)
    has_label = any(child.type == NodeType.TEXT for child in node.children)
    if not has_radio or not has_label:
        return False
    return len(node.children) <= 3


def layout_fact_payment_option_shell_column(node: CleanDesignTreeNode) -> bool:
    """Bordered option shell hosting a compact radio label row."""
    if node.type != NodeType.COLUMN:
        return False
    if not node.style.border_color and not node.style.has_stroke:
        return False
    return any(layout_fact_compact_radio_label_row(child) for child in node.children)


def layout_fact_payment_plan_primary_copy_column(node: CleanDesignTreeNode) -> bool:
    """Title/subtitle column beside a compact subscription-plan radio row."""
    if node.type != NodeType.COLUMN:
        return False
    text_children = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]
    if not (1 <= len(text_children) <= 2):
        return False
    width = node.sizing.width
    if width is None:
        return False
    return 150.0 <= float(width) <= 260.0


def layout_fact_published_star_component_host(node: CleanDesignTreeNode) -> bool:
    """Published Figma component instance whose family is a star glyph."""
    if node.variant and node.variant.component_name:
        return "star" in node.variant.component_name.lower()
    return False


def layout_fact_payment_plan_row_label_text(node: CleanDesignTreeNode) -> bool:
    """Primary plan label copy that must flex inside an ``Expanded`` slot."""
    if node.type != NodeType.TEXT:
        return False
    width = node.sizing.width
    if width is None:
        return False
    return 150.0 <= float(width) <= 260.0


def layout_fact_payment_plan_trailing_price_cluster(node: CleanDesignTreeNode) -> bool:
    """Trailing price + radio cluster beside expanded plan copy in a plan card row."""
    from figma_flutter_agent.parser.interaction import _subtree_has_currency_price

    if node.type != NodeType.ROW:
        return False
    width = node.sizing.width
    if width is None or not (72.0 <= float(width) <= 120.0):
        return False
    if not _subtree_has_currency_price(node):
        return False
    return any(
        child.type in {NodeType.ROW, NodeType.RADIO, NodeType.VECTOR, NodeType.STACK}
        for child in node.children
    )


def layout_fact_payment_plan_option_row(node: CleanDesignTreeNode) -> bool:
    """Plan card body row pairing expanded copy with a trailing price cluster."""
    if node.type != NodeType.ROW or len(node.children) < 2:
        return False
    leading = node.children[0]
    trailing = node.children[-1]
    if leading.type != NodeType.COLUMN:
        return False
    return layout_fact_payment_plan_trailing_price_cluster(trailing) or (
        layout_fact_payment_plan_primary_copy_column(leading)
        and trailing.type == NodeType.ROW
        and trailing.sizing.width is not None
        and 72.0 <= float(trailing.sizing.width) <= 120.0
    )


def layout_fact_hosts_payment_selection_indicator(node: CleanDesignTreeNode) -> bool:
    """True when a compact trailing margin hosts a circular payment radio badge."""
    if node.type != NodeType.COLUMN:
        return False
    if (node.name or "").lower() != "margin":
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (18.0 <= float(width) <= 24.0 and 20.0 <= float(height) <= 28.0):
        return False
    return node.cluster_id is not None or any(
        child.type in {NodeType.ROW, NodeType.STACK} and child.style.border_color
        for child in node.children
    )


def _subtree_has_greenish_fill(node: CleanDesignTreeNode) -> bool:
    if is_greenish_fill(node.style.background_color):
        return True
    return any(_subtree_has_greenish_fill(child) for child in node.children)


def _background_is_selection_highlight(color: str | None) -> bool:
    """Detect light green selection washes distinct from neutral card greys."""
    return is_greenish_fill(color)


def button_is_payment_option_card(node: CleanDesignTreeNode) -> bool:
    """Tappable card with a title block and trailing circular payment radio."""
    from figma_flutter_agent.parser.interaction.buttons import (
        button_has_composite_row_body,
    )
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    if node.type != NodeType.BUTTON or not node.style.background_color:
        return False
    if not button_has_composite_row_body(node):
        return False
    return any(
        layout_fact_hosts_payment_selection_indicator(item) for item in _descendant_nodes(node, 6)
    )


_COMPACT_TRAILING_SELECTION_MAX_PX = 20.0


def layout_fact_compact_trailing_selection_glyph(node: CleanDesignTreeNode) -> bool:
    """Compact list-row trailing check/radio glyph (vector-only, no label chrome)."""
    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if float(width) <= 0 or float(height) <= 0:
        return False
    if (
        float(width) > _COMPACT_TRAILING_SELECTION_MAX_PX
        or float(height) > _COMPACT_TRAILING_SELECTION_MAX_PX
    ):
        return False
    if len(node.children) != 1:
        return False
    child = node.children[0]
    if child.type not in {NodeType.VECTOR, NodeType.IMAGE}:
        return False
    return bool(child.image_asset_key or child.vector_asset_key)


def payment_selection_circle_node(root: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the bordered circular badge inside a payment selection margin column."""
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    for item in _descendant_nodes(root, 5):
        width = item.sizing.width
        height = item.sizing.height
        if width is None or height is None:
            continue
        if not (14.0 <= float(width) <= 24.0 and 14.0 <= float(height) <= 24.0):
            continue
        if abs(float(width) - float(height)) > 2.0:
            continue
        if item.style.border_color and item.style.border_width:
            return item
    return None


_BOUNDED_RADIO_GLYPH_MAX_PX = 48.0
_GENERIC_RADIO_LABELS = frozenset({"radio button", "radio"})


def _radio_has_bounded_glyph_slot(node: CleanDesignTreeNode) -> bool:
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if float(width) <= 0 or float(height) <= 0:
        return False
    return (
        float(width) <= _BOUNDED_RADIO_GLYPH_MAX_PX and float(height) <= _BOUNDED_RADIO_GLYPH_MAX_PX
    )


def layout_fact_radio_exact_paint(node: CleanDesignTreeNode) -> bool:
    """Bounded radio glyph slots must emit Figma paint, not Material Radio chrome."""
    return node.type == NodeType.RADIO and _radio_has_bounded_glyph_slot(node)


def _host_has_external_text_label(
    host: CleanDesignTreeNode,
    radio_id: str,
) -> bool:
    return any(child.type == NodeType.TEXT and child.id != radio_id for child in host.children)


def layout_fact_compact_radio_glyph(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
    *,
    ancestor_hosts: tuple[CleanDesignTreeNode, ...] | None = None,
) -> bool:
    """Radio with an external label or bounded glyph slot must not emit ListTile."""
    if node.type != NodeType.RADIO:
        return False
    if _radio_has_bounded_glyph_slot(node):
        return True
    hosts: list[CleanDesignTreeNode] = []
    if parent_node is not None:
        hosts.append(parent_node)
    if ancestor_hosts:
        hosts.extend(ancestor_hosts)
    for host in hosts:
        if host.type in _FLEX_LABEL_HOST_TYPES and _host_has_external_text_label(host, node.id):
            return True
    return False


def radio_external_semantic_label(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
    *,
    ancestor_hosts: tuple[CleanDesignTreeNode, ...] | None = None,
) -> str | None:
    """Return a non-generic external label for a compact radio glyph when present."""
    hosts: list[CleanDesignTreeNode] = []
    if parent_node is not None:
        hosts.append(parent_node)
    if ancestor_hosts:
        hosts.extend(ancestor_hosts)
    for host in hosts:
        if host.type not in _FLEX_LABEL_HOST_TYPES:
            continue
        for child in host.children:
            if child.type != NodeType.TEXT or child.id == node.id:
                continue
            label = (child.text or child.name or child.accessibility_label or "").strip()
            if label and label.lower() not in _GENERIC_RADIO_LABELS:
                return label
    return None


def payment_option_button_is_selected(node: CleanDesignTreeNode | None) -> bool:
    """Return True when an option-card button uses the selected highlight fill."""
    if node is None or node.type != NodeType.BUTTON:
        return False
    if _background_is_selection_highlight(node.style.background_color):
        return True
    return _subtree_has_greenish_fill(node)
