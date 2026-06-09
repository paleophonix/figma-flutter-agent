"""Square product-photo and summary metric row emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.parser.interaction import (
    _descendant_nodes,
    button_is_square_cart_product_thumbnail,
    extract_cart_quantity_digit,
    find_raster_photo_leaf,
    looks_like_cart_quantity_scrim_row,
    looks_like_favorite_icon_button,
    node_is_compact_percent_badge,
    stack_is_product_recommendation_hero,
    stack_is_square_product_photo_host,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _product_photo_raster_leaf(
    host: CleanDesignTreeNode,
) -> CleanDesignTreeNode | None:
    """Return the raster photo leaf inside a square cart thumbnail host."""
    leaf = find_raster_photo_leaf(host)
    if leaf is not None:
        return leaf
    if host.image_asset_key:
        return host
    for item in _descendant_nodes(host, 6):
        if item.image_asset_key:
            return item
    return None


def _stack_overlay_offset_literals(child: CleanDesignTreeNode) -> tuple[str, str]:
    """Return ``left`` and ``top`` literals for a positioned hero overlay child."""
    frame = child.geometry_frame
    if frame is not None and frame.layout_rect is not None:
        left = float(frame.layout_rect.x or 0.0)
        top = float(frame.layout_rect.y or 0.0)
        if left > 0.0 or top > 0.0:
            return format_geometry_literal(left), format_geometry_literal(top)
    placement = child.stack_placement
    if placement is not None:
        top = float(placement.top or 8.0)
        left = float(placement.left or 8.0)
        if (placement.horizontal or "LEFT").upper() == "CENTER" and left > 40.0:
            left = 8.0
        return format_geometry_literal(left), format_geometry_literal(top)
    return "8.0", "8.0"


def _hero_raster_layer(*, asset: str) -> str:
    """Emit a full-bleed hero raster preserving Figma photo proportions."""
    image = f"Image.asset('{asset}', fit: BoxFit.cover)"
    return f"Positioned.fill(child: {image})"


def _hero_scrim_carries_percent_badge(node: CleanDesignTreeNode) -> bool:
    """True when a full-bleed scrim sibling already owns the discount chip subtree."""
    from figma_flutter_agent.parser.interaction import stack_is_hero_full_bleed_scrim

    for child in node.children:
        if not stack_is_hero_full_bleed_scrim(child):
            continue
        if any(
            node_is_compact_percent_badge(item)
            for item in _descendant_nodes(child, 4)
        ):
            return True
    return False


def _hero_overlay_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Collect wishlist overlays from a product hero ``STACK``."""
    ordered: list[CleanDesignTreeNode] = []
    seen: set[str] = set()

    def consider(candidate: CleanDesignTreeNode) -> None:
        if candidate.id in seen:
            return
        if candidate.type != NodeType.BUTTON or not looks_like_favorite_icon_button(candidate):
            return
        seen.add(candidate.id)
        ordered.append(candidate)

    for child in node.children:
        consider(child)
    for descendant in _descendant_nodes(node, 4):
        consider(descendant)
    return ordered


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


def _render_metric_row_text(
    leaf: CleanDesignTreeNode,
    *,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
) -> str:
    """Emit summary label/value text without row flex wrappers."""
    from figma_flutter_agent.generator.layout.style import (
        text_align_expr,
        text_style_expr,
        text_widget_trailing_params,
    )

    style = text_style_expr(
        leaf,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
    )
    align = text_align_expr(leaf.style)
    align_suffix = f", textAlign: {align}" if align else ""
    trailing = text_widget_trailing_params(
        leaf.style,
        text_align_suffix=align_suffix,
        omit_strut=True,
    )
    label = escape_dart_string(leaf.accessibility_label or leaf.text or leaf.name)
    return (
        f"Semantics(label: '{label}', child: Text("
        f"'{escape_dart_string(leaf.text or '')}', "
        f"style: {style}, {trailing}))"
    )


def try_render_product_recommendation_hero_stack(
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
    """Edge-to-edge cover imagery with optional wishlist and discount overlays."""
    if not stack_is_product_recommendation_hero(node):
        return None
    photo = _product_photo_raster_leaf(node)
    if photo is None or not photo.image_asset_key:
        return None
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return None
    asset = escape_dart_string(photo.image_asset_key)
    overlays = _hero_overlay_nodes(node)
    layers = [_hero_raster_layer(asset=asset)]
    for child in overlays:
        if child.type == NodeType.BUTTON and looks_like_favorite_icon_button(child):
            placement = child.stack_placement
            top = format_geometry_literal(float(placement.top if placement else 8.0))
            right = format_geometry_literal(float(placement.right if placement else 8.0))
            width = format_geometry_literal(float(child.sizing.width or 32.0))
            height = format_geometry_literal(float(child.sizing.height or 32.0))
            radius = format_geometry_literal(float(child.style.border_radius or 16.0))
            layers.append(
                "Positioned("
                f"top: {top}, right: {right}, width: {width}, height: {height}, "
                "child: Semantics(label: 'Button', child: Material("
                "elevation: 0, color: Colors.transparent, child: Ink("
                f"decoration: BoxDecoration(color: Color(0xFFFFFFFF), borderRadius: BorderRadius.circular({radius})), "
                "child: InkWell("
                f"onTap: () {{ /* <custom-code:figma-{child.id.replace(':', '_')}:button-action> */ }}, "
                f"customBorder: RoundedRectangleBorder(borderRadius: BorderRadius.circular({radius})), "
                f"child: Icon(Icons.favorite_border, color: Color(0xFF3E4A3C), size: 14.4)"
                ")))))"
            )
            continue
    body = ", ".join(layers)
    return (
        "Stack(fit: StackFit.expand, clipBehavior: Clip.none, "
        f"children: [{body}])"
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

    from figma_flutter_agent.generator.layout.flex_policy.row import (
        row_child_summary_text_leaf,
    )

    leaves = [row_child_summary_text_leaf(child) for child in node.children]
    if any(leaf is None for leaf in leaves):
        return None
    rendered: list[str] = []
    for leaf in leaves:
        assert leaf is not None
        rendered.append(
            _render_metric_row_text(
                leaf,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            )
        )
    return (
        "Row("
        "mainAxisAlignment: MainAxisAlignment.spaceBetween, "
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [{', '.join(rendered)}])"
    )


def status_pill_badge_body(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    main_axis: str,
    cross_axis: str,
    flex_spacing_field: object,
) -> str:
    """Center compact pill labels without overflowing tight Figma bounds."""
    if len(child_widgets) == 1:
        width = node.sizing.width
        if width is not None and float(width) <= 56.0:
            return (
                "Center(child: FittedBox("
                "fit: BoxFit.scaleDown, "
                "alignment: Alignment.center, "
                f"child: {child_widgets[0]}))"
            )
        pad_lr = 8.0
        if node.padding is not None:
            pad_lr = max(
                float(node.padding.left or 0.0),
                float(node.padding.right or 0.0),
                pad_lr,
            )
        return (
            "Padding("
            "padding: "
            f"const EdgeInsets.symmetric(horizontal: {format_geometry_literal(pad_lr)}), "
            "child: Row("
            "mainAxisSize: MainAxisSize.min, "
            "mainAxisAlignment: MainAxisAlignment.center, "
            "crossAxisAlignment: CrossAxisAlignment.center, "
            f"children: [{child_widgets[0]}]))"
        )
    spacing_field = flex_spacing_field(node)
    return (
        f"Row(mainAxisAlignment: {main_axis}, "
        f"crossAxisAlignment: {cross_axis}, "
        f"{spacing_field}children: [{', '.join(child_widgets)}])"
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
