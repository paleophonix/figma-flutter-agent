"""Square product-photo and summary metric row emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.parser.interaction import (
    _descendant_nodes,
    button_is_square_cart_product_thumbnail,
    extract_cart_quantity_digit,
    find_raster_photo_leaf,
    looks_like_cart_quantity_scrim_row,
    stack_is_square_product_photo_host,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _product_photo_raster_leaf(
    host: CleanDesignTreeNode,
) -> CleanDesignTreeNode | None:
    """Return the raster photo leaf inside a square cart thumbnail host."""
    return find_raster_photo_leaf(host)


def _product_photo_quantity(
    host: CleanDesignTreeNode,
) -> tuple[CleanDesignTreeNode | None, str | None]:
    """Return the quantity TEXT node (when present) and its digit for cart thumbnails."""
    for child in host.children:
        if not looks_like_cart_quantity_scrim_row(child):
            continue
        digit = extract_cart_quantity_digit(child)
        if digit is None:
            continue
        for item in _descendant_nodes(child, 3):
            if item.type != NodeType.TEXT:
                continue
            text = (item.text or "").strip()
            if text.isdigit() and 0 < len(text) <= 3:
                return item, digit
        return None, digit
    return None, None


def _render_cart_quantity_layer(
    quantity_node: CleanDesignTreeNode | None,
    digit: str,
    *,
    host: CleanDesignTreeNode,
    uses_svg: bool,
    render_node_body: object,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Render centered quantity text from a TEXT node or a preserved prune digit."""
    if quantity_node is not None:
        text_body = render_node_body(
            quantity_node,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
            parent_node=host,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        return f"Center(child: {text_body})"
    escaped = escape_dart_string(digit)
    return (
        "Center(child: Text("
        f"'{escaped}', "
        "style: Theme.of(context).textTheme.bodyMedium?.copyWith("
        "color: const Color(0xFFFFFFFF), fontSize: 36.0, fontWeight: FontWeight.w600), "
        "textScaler: textScaler, textAlign: TextAlign.center))"
    )


def try_render_cart_thumbnail_button(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    render_node_body: object,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Clip a decomposed square cart thumbnail hosted inside a ``BUTTON`` frame."""
    if not button_is_square_cart_product_thumbnail(node):
        return None
    photo = _product_photo_raster_leaf(node)
    if photo is None or not photo.image_asset_key:
        return None
    quantity_node, quantity_digit = _product_photo_quantity(node)
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return None
    width_lit = format_geometry_literal(float(width))
    height_lit = format_geometry_literal(float(height))
    radius = float(node.style.border_radius or 22.0)
    radius_lit = format_geometry_literal(radius)
    asset = escape_dart_string(photo.image_asset_key)
    layers = [
        f"Image.asset('{asset}', fit: BoxFit.cover)",
        "Container(color: Color(0x3D000000))",
    ]
    if quantity_digit is not None:
        layers.append(
            _render_cart_quantity_layer(
                quantity_node,
                quantity_digit,
                host=node,
                uses_svg=uses_svg,
                render_node_body=render_node_body,
                theme_variant=theme_variant,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
        )
    body = ", ".join(layers)
    from .button import _wrap_button_stack

    thumb = (
        f"ClipRRect("
        f"borderRadius: BorderRadius.circular({radius_lit}), "
        f"child: SizedBox("
        f"width: {width_lit}, height: {height_lit}, "
        f"child: Stack(fit: StackFit.expand, children: [{body}])))"
    )
    return _wrap_button_stack(thumb, node, theme_variant=theme_variant)


def try_render_square_product_photo_stack(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None,
    uses_svg: bool,
    render_node_body: object,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Clip a square cart thumbnail with cover-fit photo and translucent quantity scrim."""
    if not stack_is_square_product_photo_host(node):
        return None
    photo = _product_photo_raster_leaf(node)
    if photo is None or not photo.image_asset_key:
        return None
    quantity_node, quantity_digit = _product_photo_quantity(node)
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return None
    width_lit = format_geometry_literal(float(width))
    height_lit = format_geometry_literal(float(height))
    radius = 22.0
    if parent_node is not None and parent_node.type == NodeType.BUTTON:
        if parent_node.style.border_radius is not None:
            radius = float(parent_node.style.border_radius)
    radius_lit = format_geometry_literal(radius)
    asset = escape_dart_string(photo.image_asset_key)
    layers = [
        f"Image.asset('{asset}', fit: BoxFit.cover)",
        "Container(color: Color(0x3D000000))",
    ]
    if quantity_digit is not None:
        layers.append(
            _render_cart_quantity_layer(
                quantity_node,
                quantity_digit,
                host=node,
                uses_svg=uses_svg,
                render_node_body=render_node_body,
                theme_variant=theme_variant,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
        )
    body = ", ".join(layers)
    return (
        f"ClipRRect("
        f"borderRadius: BorderRadius.circular({radius_lit}), "
        f"child: SizedBox("
        f"width: {width_lit}, height: {height_lit}, "
        f"child: Stack(fit: StackFit.expand, children: [{body}])))"
    )


def try_render_space_between_text_metric_row(
    node: CleanDesignTreeNode,
    *,
    child_widgets: list[str],
    uses_svg: bool,
    render_node_body: object,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Flatten label/value stacks into a centered space-between row."""
    from figma_flutter_agent.generator.layout.flex_policy import (
        row_is_space_between_text_metric_row,
    )

    if not row_is_space_between_text_metric_row(node) or len(child_widgets) != 2:
        return None

    def _leaf_text(child: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if child.type == NodeType.TEXT:
            return child
        if child.type == NodeType.STACK and len(child.children) == 1:
            leaf = child.children[0]
            if leaf.type == NodeType.TEXT:
                return leaf
        return None

    leaves = [_leaf_text(child) for child in node.children]
    if any(leaf is None for leaf in leaves):
        return None
    rendered: list[str] = []
    for leaf in leaves:
        assert leaf is not None
        rendered.append(
            render_node_body(
                leaf,
                uses_svg=uses_svg,
                parent_type=NodeType.ROW,
                parent_node=node,
                theme_variant=theme_variant,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
        )
    return (
        "Row("
        "mainAxisAlignment: MainAxisAlignment.spaceBetween, "
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [{', '.join(rendered)}])"
    )


def try_render_oversized_photo_clip_column(
    node: CleanDesignTreeNode,
) -> str | None:
    """Clip an oversized raster child to a square column host."""
    from figma_flutter_agent.generator.layout.flex_policy import (
        column_is_oversized_photo_clip_host,
    )

    if not column_is_oversized_photo_clip_host(node):
        return None
    child = node.children[0]
    asset = escape_dart_string(child.image_asset_key or "")
    width_lit = format_geometry_literal(float(node.sizing.width or 96.0))
    height_lit = format_geometry_literal(float(node.sizing.height or 96.0))
    radius = node.style.border_radius or 22.0
    radius_lit = format_geometry_literal(float(radius))
    return (
        f"ClipRRect("
        f"borderRadius: BorderRadius.circular({radius_lit}), "
        f"child: SizedBox("
        f"width: {width_lit}, height: {height_lit}, "
        f"child: Image.asset('{asset}', fit: BoxFit.cover)))"
    )
