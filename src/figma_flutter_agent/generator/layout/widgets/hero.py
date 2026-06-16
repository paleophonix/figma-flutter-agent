"""Product-recommendation hero stack and summary metric row emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.style import dart_color_expr
from figma_flutter_agent.generator.layout.style.facts import label_color_on_surface_expr
from figma_flutter_agent.parser.interaction import (
    _descendant_nodes,
    layout_fact_favorite_icon_button,
    layout_fact_stack_product_recommendation_hero,
    node_is_compact_percent_badge,
    percent_badge_should_emit_as_overlay,
)
from figma_flutter_agent.parser.interaction.icons import layout_fact_favorite_overlay_stack
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


def _detail_hero_background_child(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the primary full-bleed background leaf inside a detail hero host."""
    overlays = {
        candidate.id
        for candidate in _hero_overlay_nodes(node)
    }
    candidates: list[tuple[float, CleanDesignTreeNode]] = []
    for child in node.children:
        if child.id in overlays:
            continue
        width = child.sizing.width
        height = child.sizing.height
        if width is None or height is None or float(width) <= 0 or float(height) <= 0:
            continue
        area = float(width) * float(height)
        if child.type in {NodeType.IMAGE, NodeType.VECTOR, NodeType.CONTAINER, NodeType.STACK} and (
            child.image_asset_key or child.vector_asset_key or child.style.background_color
        ):
            candidates.append((area, child))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _detail_hero_background_layer(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    render_node_body: object,
) -> str | None:
    """Emit a full-bleed hero background when no raster photo leaf is available."""
    background = _detail_hero_background_child(node)
    if background is None:
        return None
    if background.image_asset_key:
        asset = escape_dart_string(background.image_asset_key)
        return _hero_raster_layer(asset=asset)
    if uses_svg and background.vector_asset_key:
        from figma_flutter_agent.generator.layout.widgets.svg import _render_svg_picture

        width_lit = format_geometry_literal(float(background.sizing.width or node.sizing.width or 0.0))
        height_lit = format_geometry_literal(float(background.sizing.height or node.sizing.height or 0.0))
        picture = _render_svg_picture(
            background,
            escape_dart_string(background.vector_asset_key),
        )
        return (
            f"Positioned.fill(child: SizedBox(width: {width_lit}, height: {height_lit}, "
            f"child: {picture}))"
        )
    if render_node_body is not None:
        body = render_node_body(
            background,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
            parent_node=node,
        )
        return f"Positioned.fill(child: {body})"
    return None


def _emit_detail_hero_banner_stack(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    render_node_body: object,
    theme_variant: str,
) -> str | None:
    """Shared detail-hero emitter for raster or vector backgrounds plus overlays."""
    from figma_flutter_agent.parser.interaction.product import (
        layout_fact_stack_detail_hero_banner_host,
    )

    if not layout_fact_stack_detail_hero_banner_host(node):
        return None
    photo = _product_photo_raster_leaf(node)
    layers: list[str] = []
    if photo is not None and photo.image_asset_key:
        layers.append(_hero_raster_layer(asset=escape_dart_string(photo.image_asset_key)))
    else:
        background = _detail_hero_background_layer(
            node,
            uses_svg=uses_svg,
            render_node_body=render_node_body,
        )
        if background is None:
            return None
        layers.append(background)
    for child in _hero_overlay_nodes(node):
        if child.type == NodeType.BUTTON and layout_fact_favorite_icon_button(child):
            layers.append(_render_favorite_button_overlay(child, theme_variant=theme_variant))
            continue
        if child.type == NodeType.STACK and layout_fact_favorite_overlay_stack(child):
            layers.append(
                _render_favorite_overlay_stack(
                    child,
                    uses_svg=uses_svg,
                    theme_variant=theme_variant,
                )
            )
            continue
        if node_is_compact_percent_badge(child):
            overlay = _render_percent_badge_overlay(child)
            if overlay is not None:
                layers.append(overlay)
    body = ", ".join(layers)
    return f"Stack(fit: StackFit.expand, clipBehavior: Clip.none, children: [{body}])"


def _render_favorite_button_overlay(
    child: CleanDesignTreeNode,
    *,
    theme_variant: str,
) -> str:
    """Render a positioned favorite/wishlist BUTTON overlay."""
    placement = child.stack_placement
    top = format_geometry_literal(float(placement.top if placement else 8.0))
    right = format_geometry_literal(float(placement.right if placement else 8.0))
    btn_width = format_geometry_literal(float(child.sizing.width or 32.0))
    btn_height = format_geometry_literal(float(child.sizing.height or 32.0))
    radius = format_geometry_literal(float(child.style.border_radius or 16.0))
    bg_expr = dart_color_expr(
        child.style,
        fallback="Theme.of(context).colorScheme.surface",
    )
    vector = next(
        (item for item in _descendant_nodes(child, 2) if item.type == NodeType.VECTOR),
        None,
    )
    icon_color = (
        dart_color_expr(
            vector.style,
            fallback="Theme.of(context).colorScheme.onSurface",
        )
        if vector is not None
        else "Theme.of(context).colorScheme.onSurface"
    )
    icon_size = format_geometry_literal(
        float(vector.sizing.width or 14.4) if vector is not None else 14.4
    )
    from figma_flutter_agent.generator.layout.cupertino import wrap_button_stack

    body = (
        "Material("
        "elevation: 0, color: Colors.transparent, child: Ink("
        f"decoration: BoxDecoration(color: {bg_expr}, borderRadius: BorderRadius.circular({radius})), "
        "child: InkWell("
        f"onTap: () {{ /* <custom-code:figma-{child.id.replace(':', '_')}:button-action> */ }}, "
        f"customBorder: RoundedRectangleBorder(borderRadius: BorderRadius.circular({radius})), "
        f"child: Icon(Icons.favorite_border, color: {icon_color}, size: {icon_size})"
        ")))"
    )
    wrapped = wrap_button_stack(
        body,
        theme_variant=theme_variant,
        border_radius=float(child.style.border_radius or 16.0),
        node_id=child.id,
        tap_role="button-action",
    )
    return (
        f"Positioned(top: {top}, right: {right}, width: {btn_width}, height: {btn_height}, "
        f"child: Semantics(button: true, label: 'Button', child: {wrapped}))"
    )


def _render_favorite_overlay_stack(
    child: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str,
) -> str:
    """Render a positioned favorite/save STACK overlay with tap affordance."""
    from figma_flutter_agent.generator.layout.cupertino import wrap_button_stack
    from figma_flutter_agent.generator.layout.widgets.svg import _render_svg_picture

    placement = child.stack_placement
    top = format_geometry_literal(float(placement.top if placement else 8.0))
    right = format_geometry_literal(float(placement.right if placement else 8.0))
    btn_width = format_geometry_literal(float(child.sizing.width or 37.0))
    btn_height = format_geometry_literal(float(child.sizing.height or 37.0))
    local_nodes = _descendant_nodes(child, 3)
    painted = next(
        (
            item
            for item in local_nodes
            if item.style.background_color
            and item.type in {NodeType.CONTAINER, NodeType.STACK}
        ),
        child,
    )
    radius = format_geometry_literal(
        float(painted.style.border_radius or min(float(child.sizing.width or 37.0), 37.0) / 2.0)
    )
    bg_expr = dart_color_expr(
        painted.style,
        fallback="Theme.of(context).colorScheme.surface",
    )
    vector_asset = next((item for item in local_nodes if item.vector_asset_key), None)
    if uses_svg and vector_asset is not None and vector_asset.vector_asset_key:
        icon = _render_svg_picture(
            vector_asset,
            escape_dart_string(vector_asset.vector_asset_key),
        )
    else:
        vector = next((item for item in local_nodes if item.type == NodeType.VECTOR), None)
        icon_color = (
            dart_color_expr(
                vector.style,
                fallback="Theme.of(context).colorScheme.onSurface",
            )
            if vector is not None
            else "Theme.of(context).colorScheme.onSurface"
        )
        icon_size = format_geometry_literal(
            float(vector.sizing.width or 14.4) if vector is not None else 14.4
        )
        icon = f"Icon(Icons.favorite_border, color: {icon_color}, size: {icon_size})"
    body = (
        "Material("
        "elevation: 0, color: Colors.transparent, child: Ink("
        f"decoration: BoxDecoration(color: {bg_expr}, borderRadius: BorderRadius.circular({radius})), "
        f"child: Center(child: {icon}))"
        ")"
    )
    wrapped = wrap_button_stack(
        body,
        theme_variant=theme_variant,
        border_radius=float(painted.style.border_radius or 18.0),
        node_id=child.id,
        tap_role="button-action",
    )
    return (
        f"Positioned(top: {top}, right: {right}, width: {btn_width}, height: {btn_height}, "
        f"child: Semantics(button: true, label: 'Button', child: {wrapped}))"
    )


def _hero_overlay_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Collect wishlist and discount-badge overlays from a product hero ``STACK``."""
    ordered: list[CleanDesignTreeNode] = []
    seen: set[str] = set()

    def visit(candidate: CleanDesignTreeNode, depth: int) -> None:
        if candidate.id in seen:
            return
        if candidate.type == NodeType.BUTTON and layout_fact_favorite_icon_button(candidate):
            seen.add(candidate.id)
            ordered.append(candidate)
            return
        if candidate.type == NodeType.STACK and layout_fact_favorite_overlay_stack(candidate):
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
    badge_bg = dart_color_expr(
        node.style,
        fallback="Theme.of(context).colorScheme.primary",
    )
    text_color = label_color_on_surface_expr(
        label.style,
        surface_color=node.style.background_color,
    )
    text_style = f"Theme.of(context).textTheme.labelSmall?.copyWith(color: {text_color})"
    return (
        f"Positioned(top: {top}, left: {left}, "
        "child: Container("
        f"decoration: BoxDecoration(color: {badge_bg}, "
        f"borderRadius: BorderRadius.circular({radius})), "
        "padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0), "
        f"child: Text('{text}', "
        f"style: {text_style})))"
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
    if not layout_fact_stack_product_recommendation_hero(node):
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
        if child.type == NodeType.BUTTON and layout_fact_favorite_icon_button(child):
            layers.append(_render_favorite_button_overlay(child, theme_variant=theme_variant))
            continue
        if child.type == NodeType.STACK and layout_fact_favorite_overlay_stack(child):
            layers.append(
                _render_favorite_overlay_stack(
                    child,
                    uses_svg=uses_svg,
                    theme_variant=theme_variant,
                )
            )
            continue
        if node_is_compact_percent_badge(child):
            overlay = _render_percent_badge_overlay(child)
            if overlay is not None:
                layers.append(overlay)
            continue
    body = ", ".join(layers)
    return f"Stack(fit: StackFit.expand, clipBehavior: Clip.none, children: [{body}])"


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
        layout_fact_row_space_between_text_metric_row,
    )

    if not layout_fact_row_space_between_text_metric_row(node) or len(child_widgets) != 2:
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


def try_render_detail_hero_banner_stack(
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
    """Wide detail hero banners with raster or vector cover and interactive overlays."""
    _ = (
        bundled_font_families,
        dart_weight_overrides_by_family,
        text_theme_slot_by_style_name,
        text_theme_size_slots,
    )
    return _emit_detail_hero_banner_stack(
        node,
        uses_svg=uses_svg,
        render_node_body=render_node_body,
        theme_variant=theme_variant,
    )


def try_render_compact_icon_label_metric_stack(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Emit a tight icon+label metric row without overlapping absolute placements."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_stack_compact_icon_label_metric,
    )
    from figma_flutter_agent.generator.layout.widgets.svg import _render_svg_picture

    if not layout_fact_stack_compact_icon_label_metric(node):
        return None
    text_nodes = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]
    icon_nodes = [
        child
        for child in node.children
        if child.type in {NodeType.VECTOR, NodeType.IMAGE}
        or child.vector_asset_key
        or child.image_asset_key
    ]
    if len(text_nodes) != 1 or not icon_nodes:
        return None
    icon = icon_nodes[0]
    text = text_nodes[0]
    if uses_svg and icon.vector_asset_key:
        icon_widget = _render_svg_picture(icon, escape_dart_string(icon.vector_asset_key))
    elif icon.image_asset_key:
        asset = escape_dart_string(icon.image_asset_key)
        icon_width = icon.sizing.width
        icon_height = icon.sizing.height
        size_params = ""
        if icon_width is not None and icon_height is not None:
            size_params = (
                f"width: {format_geometry_literal(float(icon_width))}, "
                f"height: {format_geometry_literal(float(icon_height))}, "
            )
        icon_widget = f"Image.asset('{asset}', {size_params}fit: BoxFit.contain)"
    else:
        icon_widget = "const SizedBox.shrink()"
    text_widget = _render_metric_row_text(
        text,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
    )
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return None
    width_lit = format_geometry_literal(float(width))
    height_lit = format_geometry_literal(float(height))
    return (
        f"SizedBox(width: {width_lit}, height: {height_lit}, "
        "child: Row("
        "mainAxisSize: MainAxisSize.max, "
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [{icon_widget}, Expanded(child: {text_widget})]"
        "))"
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
            float(node.padding.left or 0.0) > 0.0 and float(node.padding.right or 0.0) > 0.0
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
