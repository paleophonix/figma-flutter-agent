"""Product card and cart predicates."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.facts import is_near_black_fill
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .icons import layout_fact_favorite_glyph_vector
from .shared import (
    _argb_color_key,
    _descendant_nodes,
)


def layout_fact_favorite_glyph_vector_re_export(node: CleanDesignTreeNode) -> bool:  # noqa: F401 — re-exported via __init__
    return layout_fact_favorite_glyph_vector(node)


def layout_fact_cart_quantity_scrim_row(node: CleanDesignTreeNode) -> bool:
    """Square black scrim row layered over a cart product thumbnail."""
    if node.type != NodeType.ROW:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) < 64.0 or float(height) < 64.0:
        return False
    if abs(float(width) - float(height)) > max(8.0, float(width) * 0.12):
        return False
    return is_near_black_fill(node.style.background_color)


def _subtree_has_currency_price(node: CleanDesignTreeNode, *, max_depth: int = 4) -> bool:
    """Return True when a subtree contains product price copy with a currency marker."""
    if max_depth < 0:
        return False
    if node.type == NodeType.TEXT:
        text = (node.text or "").strip()
        if text and any(symbol in text for symbol in ("₽", "$", "€", "£", "¥", "₴", "₸")):
            return True
    return any(
        _subtree_has_currency_price(child, max_depth=max_depth - 1) for child in node.children
    )


def _subtree_has_product_price_copy(node: CleanDesignTreeNode, *, max_depth: int = 4) -> bool:
    """Return True when a subtree contains currency or numeric product price copy."""
    from .text_actions import price_or_value_label_fact

    if max_depth < 0:
        return False
    if node.type == NodeType.TEXT:
        text = (node.text or "").strip()
        if text and (
            any(symbol in text for symbol in ("₽", "$", "€", "£", "¥", "₴", "₸"))
            or price_or_value_label_fact(text)
        ):
            return True
    return any(
        _subtree_has_product_price_copy(child, max_depth=max_depth - 1) for child in node.children
    )


_MIN_CHECKOUT_FOOTER_CTA_WIDTH = 180.0


def _checkout_footer_has_wide_cta(node: CleanDesignTreeNode) -> bool:
    """Return True when checkout footer chrome includes a full-width payment CTA."""
    from figma_flutter_agent.generator.layout.navigation.items import collect_bottom_nav_items

    if node.type == NodeType.BOTTOM_NAV:
        items = collect_bottom_nav_items(node)
        if not items:
            return False
        candidates = items
    else:
        candidates = list(_descendant_nodes(node, max_depth=3))
    return any(
        item.type == NodeType.BUTTON
        and item.sizing.width is not None
        and float(item.sizing.width) >= _MIN_CHECKOUT_FOOTER_CTA_WIDTH
        for item in candidates
    )


def layout_fact_checkout_sticky_footer_host(node: CleanDesignTreeNode) -> bool:
    """Return True for checkout payment footer chrome on stack or demoted bottom-nav hosts."""
    if node.type not in {NodeType.BOTTOM_NAV, NodeType.STACK}:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) < 200.0 or float(height) < 56.0:
        return False
    if not _subtree_has_product_price_copy(node):
        return False
    return _checkout_footer_has_wide_cta(node)


def layout_fact_bottom_nav_is_checkout_footer(node: CleanDesignTreeNode) -> bool:
    """Return True when a bottom-nav host is checkout chrome, not peer tab destinations."""
    if node.type != NodeType.BOTTOM_NAV:
        return False
    return layout_fact_checkout_sticky_footer_host(node)


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
    from figma_flutter_agent.generator.layout.style.colors import fill_luminance

    if node.cluster_id:
        return True
    for item in [node, *_descendant_nodes(node, 3)]:
        if item.cluster_id:
            return True
        if item.type == NodeType.VECTOR:
            return True
        bg = _argb_color_key(item.style.background_color)
        luminance = fill_luminance(bg)
        if luminance is not None and luminance < 0.95:
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
    """Return True for explicit compact discount nodes layered on product imagery."""
    _ = hero
    return node_is_compact_percent_badge(badge)


def stepper_stack_intrinsic_width(node: CleanDesignTreeNode) -> float | None:
    """Return the compiled pill width of a compact quantity stepper under ``node``."""
    from figma_flutter_agent.generator.layout.widgets.stepper import (
        compact_quantity_stepper_emit_width,
    )

    if layout_fact_stack_compact_quantity_stepper(node):
        return compact_quantity_stepper_emit_width(node)
    for item in _descendant_nodes(node, 4):
        if layout_fact_stack_compact_quantity_stepper(item):
            return compact_quantity_stepper_emit_width(item)
    return None


def layout_fact_stack_hero_full_bleed_scrim(node: CleanDesignTreeNode) -> bool:
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


def layout_fact_stack_product_recommendation_hero(node: CleanDesignTreeNode) -> bool:
    """Square product-card imagery hosts with optional badge and wishlist affordances."""
    from figma_flutter_agent.generator.ir.passes.sectionize import is_sectionize_band_wrapper_id

    from .enrichment import find_raster_photo_leaf

    if is_sectionize_band_wrapper_id(node.id):
        return False
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


def layout_fact_stack_product_purchase_footer_panel(node: CleanDesignTreeNode) -> bool:
    """Wide bottom purchase chrome with price and CTA or quantity controls.

    Product-detail footers share the wide aspect ratio of hero banners but must
    keep absolutely positioned price, stepper, and cart button children instead
    of routing through the hero banner emitter.
    """
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) < 200.0 or float(height) < 72.0:
        return False
    if float(width) / float(height) < 1.2:
        return False
    if not _subtree_has_product_price_copy(node):
        return False
    has_cta = any(item.type == NodeType.BUTTON for item in _descendant_nodes(node, max_depth=2))
    has_stepper = any(
        layout_fact_stack_compact_quantity_stepper(item)
        for item in _descendant_nodes(node, max_depth=3)
    )
    return has_cta or has_stepper


_DETAIL_HERO_BANNER_MIN_ASPECT = 1.2
_DETAIL_HERO_BANNER_MAX_ASPECT = 3.0


def _stack_hosts_horizontal_product_carrier_row(node: CleanDesignTreeNode) -> bool:
    """Return True when a stack hosts a wide multi-tile product row (carousel body)."""
    from figma_flutter_agent.schemas import NodeType

    if node.type != NodeType.STACK:
        return False
    host_w = node.sizing.width
    if (host_w is None or float(host_w) <= 0) and node.stack_placement is not None:
        host_w = node.stack_placement.width
    if host_w is None or float(host_w) <= 0:
        return False
    host_w = float(host_w)
    for child in node.children:
        if child.type not in {NodeType.ROW, NodeType.COLUMN}:
            continue
        child_w = child.sizing.width
        if child_w is None or float(child_w) <= host_w + 0.5:
            continue
        product_like = sum(1 for item in child.children if horizontal_scroll_product_tile(item))
        if product_like >= 2:
            return True
    return False


def horizontal_scroll_product_tile(node: CleanDesignTreeNode) -> bool:
    """Return True when a flex child looks like a catalog/product tile."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_has_edge_to_edge_hero_stack,
    )
    from figma_flutter_agent.parser.interaction.icons import (
        layout_fact_stack_category_component_tile,
    )
    from figma_flutter_agent.schemas import NodeType

    if node.type == NodeType.CARD:
        return True
    if layout_fact_stack_category_component_tile(node):
        return True
    if layout_fact_stack_component_catalog_product_tile(node):
        return True
    return card_has_edge_to_edge_hero_stack(node)


def layout_fact_stack_component_catalog_product_tile(node: CleanDesignTreeNode) -> bool:
    """Component-backed vertical product cards used in horizontal upsell carousels."""
    from figma_flutter_agent.parser.interaction.icons import (
        layout_fact_stack_category_component_tile,
    )

    if node.type != NodeType.STACK:
        return False
    if layout_fact_stack_category_component_tile(node):
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    span_w = float(width)
    span_h = float(height)
    if not (100.0 <= span_w <= 200.0 and 150.0 <= span_h <= 300.0):
        return False
    if node.component_ref is None and node.variant is None:
        return False
    has_image = any(
        item.type == NodeType.IMAGE or item.image_asset_key
        for item in _descendant_nodes(node, max_depth=4)
    )
    has_title = any(
        item.type == NodeType.TEXT and (item.text or "").strip() for item in node.children
    )
    return has_image and has_title


def layout_fact_stack_detail_hero_banner_host(node: CleanDesignTreeNode) -> bool:
    """Wide product-detail hero hosts (raster or vector background)."""
    from .icons import layout_fact_stack_category_component_tile

    if layout_fact_stack_product_purchase_footer_panel(node):
        return False
    if node.scroll_axis == "horizontal":
        return False
    if _stack_hosts_horizontal_product_carrier_row(node):
        return False
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return False
    if float(width) < 200.0 or float(height) < 80.0:
        return False
    aspect = float(width) / float(height)
    if aspect < _DETAIL_HERO_BANNER_MIN_ASPECT or aspect > _DETAIL_HERO_BANNER_MAX_ASPECT:
        return False
    category_tiles = [
        child for child in node.children if layout_fact_stack_category_component_tile(child)
    ]
    return len(category_tiles) < 2


def layout_fact_stack_detail_hero_banner(node: CleanDesignTreeNode) -> bool:
    """Wide product-detail hero hosts with edge-to-edge raster imagery."""
    from .enrichment import find_raster_photo_leaf

    return (
        layout_fact_stack_detail_hero_banner_host(node) and find_raster_photo_leaf(node) is not None
    )


def layout_fact_stack_compact_quantity_stepper(node: CleanDesignTreeNode) -> bool:
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
    vector_controls = sum(1 for item in _descendant_nodes(node, 3) if item.type == NodeType.VECTOR)
    if vector_controls >= 2:
        control_children = max(control_children, 2)
    return control_children >= 2 and has_pill_shell


def _row_child_hosts_vector_glyph(child: CleanDesignTreeNode) -> bool:
    if child.type in {NodeType.VECTOR, NodeType.IMAGE}:
        return True
    if child.type in {NodeType.STACK, NodeType.ROW, NodeType.COLUMN}:
        return any(
            item.type in {NodeType.VECTOR, NodeType.IMAGE}
            for item in _descendant_nodes(child, max_depth=2)
        )
    return False


def _row_child_hosts_right_aligned_value_text(child: CleanDesignTreeNode) -> bool:
    if child.type == NodeType.TEXT:
        text = (child.text or "").strip()
        if not text:
            return False
        return (child.style.text_align or "LEFT").upper() == "RIGHT"
    if child.type in {NodeType.STACK, NodeType.ROW, NodeType.COLUMN}:
        for item in _descendant_nodes(child, max_depth=2):
            if item.type != NodeType.TEXT or not (item.text or "").strip():
                continue
            return (item.style.text_align or "LEFT").upper() == "RIGHT"
    return False


def layout_fact_row_leading_glyph_value_row(node: CleanDesignTreeNode) -> bool:
    """Currency or icon glyph beside a right-aligned numeric value row."""
    if node.type != NodeType.ROW or len(node.children) < 2:
        return False
    if not _row_child_hosts_vector_glyph(node.children[0]):
        return False
    return any(_row_child_hosts_right_aligned_value_text(child) for child in node.children[1:])


def layout_fact_row_product_card_price_footer_row(node: CleanDesignTreeNode) -> bool:
    """Price column paired with a compact quantity stepper inside a product tile."""
    if node.type != NodeType.ROW or len(node.children) < 2:
        return False
    price_side = node.children[0]
    action_side = node.children[-1]

    def _hosts_stepper(host: CleanDesignTreeNode) -> bool:
        if layout_fact_stack_compact_quantity_stepper(host):
            return True
        return any(
            layout_fact_stack_compact_quantity_stepper(item) for item in _descendant_nodes(host, 3)
        )

    return _subtree_has_currency_price(price_side) and _hosts_stepper(action_side)


def layout_fact_stack_square_product_photo_host(node: CleanDesignTreeNode) -> bool:
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
        if layout_fact_cart_quantity_scrim_row(child) and extract_cart_quantity_digit(child):
            has_overlay = True
            continue
        if child.type == NodeType.IMAGE and child.image_asset_key:
            has_photo = True
        elif child.type == NodeType.COLUMN:
            for grand in child.children:
                if grand.type == NodeType.IMAGE and grand.image_asset_key:
                    has_photo = True
    return has_photo and has_overlay
