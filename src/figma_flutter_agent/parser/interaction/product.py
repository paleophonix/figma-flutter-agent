"""Product card and cart predicates."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .icons import looks_like_favorite_glyph_vector
from .shared import (
    _argb_color_key,
    _descendant_nodes,
)


def looks_like_favorite_glyph_vector_re_export(node: CleanDesignTreeNode) -> bool:  # noqa: F401 — re-exported via __init__
    return looks_like_favorite_glyph_vector(node)


def looks_like_cart_quantity_scrim_row(node: CleanDesignTreeNode) -> bool:
    """Square black scrim row layered over a cart product thumbnail."""
    if node.type != NodeType.ROW:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) < 64.0 or float(height) < 64.0:
        return False
    if abs(float(width) - float(height)) > max(8.0, float(width) * 0.12):
        return False
    return _argb_color_key(node.style.background_color) == "0xFF000000"


def _subtree_has_currency_price(node: CleanDesignTreeNode, *, max_depth: int = 4) -> bool:
    """Return True when a subtree contains product price copy with a currency marker."""
    if max_depth < 0:
        return False
    if node.type == NodeType.TEXT:
        text = (node.text or "").strip()
        if text and any(symbol in text for symbol in ("₽", "$", "€", "£", "¥", "₴", "₸")):
            return True
    return any(
        _subtree_has_currency_price(child, max_depth=max_depth - 1)
        for child in node.children
    )


def node_is_compact_percent_badge(node: CleanDesignTreeNode) -> bool:
    """Small green discount chips such as ``-20%`` on product imagery."""
    if node.type not in {NodeType.COLUMN, NodeType.ROW, NodeType.CONTAINER}:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if float(width) > 80.0 or float(height) > 36.0:
        return False
    for item in _descendant_nodes(node, 2):
        if item.type != NodeType.TEXT:
            continue
        text = (item.text or "").strip()
        if "%" in text and len(text) <= 8:
            return True
    return False


def percent_badge_has_structural_paint(node: CleanDesignTreeNode) -> bool:
    """Return True when a percent chip has its own vector/fill, not OCR text on a raster."""
    if node.cluster_id:
        return True
    for item in [node, *_descendant_nodes(node, 3)]:
        if item.cluster_id:
            return True
        if item.type == NodeType.VECTOR:
            return True
        bg = _argb_color_key(item.style.background_color)
        if bg and bg not in {"0xFFFFFFFF", "0x00FFFFFF"}:
            return True
    return False


def hero_primary_raster_covers_frame(hero: CleanDesignTreeNode) -> bool:
    """Return True when an exported photo raster already paints the hero frame."""
    from .enrichment import find_raster_photo_leaf

    photo = find_raster_photo_leaf(hero)
    if photo is None or not photo.image_asset_key:
        return False
    hero_w = float(hero.sizing.width or 0.0)
    hero_h = float(hero.sizing.height or 0.0)
    if hero_w <= 0.0 or hero_h <= 0.0:
        return False
    photo_w = float(photo.sizing.width or hero_w)
    photo_h = float(photo.sizing.height or hero_h)
    placement = photo.stack_placement
    if placement is not None:
        if placement.width is not None and float(placement.width) > 0:
            photo_w = float(placement.width)
        if placement.height is not None and float(placement.height) > 0:
            photo_h = float(placement.height)
    return photo_w >= hero_w * 0.85 and photo_h >= hero_h * 0.85


def percent_badge_should_emit_as_overlay(
    badge: CleanDesignTreeNode,
    hero: CleanDesignTreeNode,
) -> bool:
    """Skip duplicate badges when discount pixels are already in the exported raster."""
    from .enrichment import find_raster_photo_leaf

    if not node_is_compact_percent_badge(badge):
        return False
    if hero_primary_raster_covers_frame(hero):
        return False
    if percent_badge_has_structural_paint(badge):
        return True
    photo = find_raster_photo_leaf(hero)
    if photo is not None and photo.image_asset_key:
        return False
    return True


def stepper_stack_intrinsic_width(node: CleanDesignTreeNode) -> float | None:
    """Return the compiled pill width of a compact quantity stepper under ``node``."""
    from figma_flutter_agent.generator.layout.widgets.stepper import (
        compact_quantity_stepper_emit_width,
    )

    if stack_is_compact_quantity_stepper(node):
        return compact_quantity_stepper_emit_width(node)
    for item in _descendant_nodes(node, 4):
        if stack_is_compact_quantity_stepper(item):
            return compact_quantity_stepper_emit_width(item)
    return None


def stack_is_hero_full_bleed_scrim(node: CleanDesignTreeNode) -> bool:
    """Full-bleed tint/blur overlay inside a product hero (badge emitted separately)."""
    if node.type != NodeType.STACK:
        return False
    if not node.style.background_color:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    return float(width) >= 100.0 and float(height) >= 100.0


def stack_is_product_recommendation_hero(node: CleanDesignTreeNode) -> bool:
    """Square product-card imagery hosts with optional badge and wishlist affordances."""
    from .enrichment import find_raster_photo_leaf

    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if float(width) < 100.0 or float(height) < 100.0:
        return False
    if abs(float(width) - float(height)) > 24.0:
        return False
    if find_raster_photo_leaf(node) is not None:
        return True
    return bool(node.cluster_id) and bool(node.children) and float(height) >= 100.0


def stack_is_compact_quantity_stepper(node: CleanDesignTreeNode) -> bool:
    """Product-card quantity pills modeled as overlapping absolute stacks in Figma."""
    from .enrichment import extract_cart_quantity_digit

    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (90.0 <= float(width) <= 220.0 and 24.0 <= float(height) <= 56.0):
        return False
    if extract_cart_quantity_digit(node) is None:
        return False
    for item in _descendant_nodes(node, 3):
        if item.type == NodeType.TEXT and "%" in (item.text or ""):
            return False
    control_children = 0
    has_pill_shell = False
    for child in node.children:
        if child.type in {NodeType.BUTTON, NodeType.VECTOR} or child.cluster_id:
            control_children += 1
        radius = child.style.border_radius
        if child.type in {NodeType.CONTAINER, NodeType.ROW, NodeType.COLUMN} and (
            radius is not None and float(radius) >= 12.0
        ):
            has_pill_shell = True
    vector_controls = sum(
        1 for item in _descendant_nodes(node, 3) if item.type == NodeType.VECTOR
    )
    if vector_controls >= 2:
        control_children = max(control_children, 2)
    return control_children >= 2 and has_pill_shell


def row_is_product_card_price_footer_row(node: CleanDesignTreeNode) -> bool:
    """Price column paired with a compact quantity stepper inside a product tile."""
    if node.type != NodeType.ROW or len(node.children) < 2:
        return False
    price_side = node.children[0]
    action_side = node.children[-1]

    def _hosts_stepper(host: CleanDesignTreeNode) -> bool:
        if stack_is_compact_quantity_stepper(host):
            return True
        return any(
            stack_is_compact_quantity_stepper(item)
            for item in _descendant_nodes(host, 3)
        )

    return _subtree_has_currency_price(price_side) and _hosts_stepper(action_side)


def stack_is_square_product_photo_host(node: CleanDesignTreeNode) -> bool:
    """Square cart thumbnail stacks that layer a raster photo and quantity scrim."""
    from .enrichment import extract_cart_quantity_digit

    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) < 64.0 or float(height) < 64.0:
        return False
    if abs(float(width) - float(height)) > max(8.0, float(width) * 0.12):
        return False
    has_photo = False
    has_overlay = False
    for child in node.children:
        if looks_like_cart_quantity_scrim_row(child) and extract_cart_quantity_digit(child):
            has_overlay = True
            continue
        if child.type == NodeType.IMAGE and child.image_asset_key:
            has_photo = True
        elif child.type == NodeType.COLUMN:
            for grand in child.children:
                if grand.type == NodeType.IMAGE and grand.image_asset_key:
                    has_photo = True
    return has_photo and has_overlay
