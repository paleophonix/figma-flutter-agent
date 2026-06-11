"""Product-recommendation hero stack and summary metric row emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.parser.interaction import (
    _descendant_nodes,
    looks_like_favorite_icon_button,
    node_is_compact_percent_badge,
    percent_badge_should_emit_as_overlay,
    stack_is_product_recommendation_hero,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .thumbnail import _product_photo_raster_leaf


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


def _hero_overlay_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Collect wishlist and discount-badge overlays from a product hero ``STACK``."""
    ordered: list[CleanDesignTreeNode] = []
    seen: set[str] = set()

    def visit(candidate: CleanDesignTreeNode, depth: int) -> None:
        if candidate.id in seen:
            return
        if candidate.type == NodeType.BUTTON and looks_like_favorite_icon_button(candidate):
            seen.add(candidate.id)
            ordered.append(candidate)
            return
        if node_is_compact_percent_badge(candidate) and percent_badge_should_emit_as_overlay(
            candidate,
            node,
        ):
            seen.add(candidate.id)
            ordered.append(candidate)
            return
        if depth >= 4:
            return
        for child in candidate.children:
            visit(child, depth + 1)

    for child in node.children:
        visit(child, 1)
    return ordered


def _render_percent_badge_overlay(node: CleanDesignTreeNode) -> str | None:
    """Render a compact discount-percent badge as a ``Positioned`` overlay."""
    label = next(
        (
            item
            for item in _descendant_nodes(node, 2)
            if item.type == NodeType.TEXT and "%" in (item.text or "")
        ),
        None,
    )
    if label is None:
        return None
    left, top = _stack_overlay_offset_literals(node)
    radius = format_geometry_literal(float(node.style.border_radius or 8.0))
    text = escape_dart_string(label.text or "")
    return (
        f"Positioned(top: {top}, left: {left}, "
        "child: Container("
        "decoration: BoxDecoration(color: Color(0xFF28A745), "
        f"borderRadius: BorderRadius.circular({radius})), "
        "padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0), "
        f"child: Text('{text}', "
        "style: TextStyle(color: Color(0xFFFFFFFF), fontSize: 12.0, fontWeight: FontWeight.w600))))"
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
        if node_is_compact_percent_badge(child):
            overlay = _render_percent_badge_overlay(child)
            if overlay is not None:
                layers.append(overlay)
            continue
    body = ", ".join(layers)
    return (
        "Stack(fit: StackFit.expand, clipBehavior: Clip.none, "
        f"children: [{body}])"
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
        has_horizontal_padding = node.padding is not None and (
            float(node.padding.left or 0.0) > 0.0
            and float(node.padding.right or 0.0) > 0.0
        )
        if not has_horizontal_padding and width is not None and float(width) <= 56.0:
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
