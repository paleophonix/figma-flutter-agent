"""Simple control branches, CARD, TABS/CAROUSEL/BOTTOM_NAV/WRAP, GRID, and misc/fallback."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.form import (
    render_checkbox,
    render_dialog,
    render_dropdown,
    render_radio,
    render_radio_group,
    render_segmented_control_host,
    render_slider,
    render_switch,
)
from figma_flutter_agent.generator.layout.navigation.tabs import render_carousel, render_tabs
from figma_flutter_agent.generator.layout.scroll import render_grid_view
from figma_flutter_agent.generator.layout.style import (
    border_radius_expr,
    box_decoration_expr,
    card_elevation_expr,
    card_emit_needs_material_shell,
    dart_color_expr,
)
from figma_flutter_agent.parser.interaction import (
    layout_fact_checkbox_control,
    layout_fact_compact_icon_action_button,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..decoration import _render_stroke_glyph_fallback
from ..finalize import _finalize_widget
from ..input import _find_icon_glyph_expr
from ..playback import (
    _should_suppress_playback_slider_node,
)
from ..position import _render_leaf_surface
from ..svg import (
    _render_exported_vector,
    _render_svg_picture,
    _should_prefer_exported_svg,
)


def render_simple_controls(
    node: CleanDesignTreeNode, ctx: dict[str, Any], flow: dict[str, Any]
) -> str | None:
    """Render CHECKBOX/SWITCH/RADIO_GROUP/RADIO/DROPDOWN/DIALOG/SLIDER/BUTTON/INPUT/CONTAINER-checkbox.

    Returns None if the node type does not match any of these branches.
    """
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    scroll_content_root = flow["scroll_content_root"]
    child_widgets = flow["child_widgets"]
    theme_variant = ctx["theme_variant"]

    if node.type == NodeType.CHECKBOX:
        widget = render_checkbox(node, theme_variant=theme_variant)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.SWITCH:
        from figma_flutter_agent.generator.layout.flex_policy.row import (
            layout_fact_switch_hosts_segmented_options,
        )

        if layout_fact_switch_hosts_segmented_options(node):
            widget = render_segmented_control_host(
                node,
                child_widgets,
                theme_variant=theme_variant,
            )
        else:
            widget = render_switch(node, theme_variant=theme_variant)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.RADIO_GROUP:
        widget = render_radio_group(node, theme_variant=theme_variant)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.RADIO:
        widget = render_radio(
            node,
            theme_variant=theme_variant,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.DROPDOWN:
        widget = render_dropdown(node, theme_variant=theme_variant)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.DIALOG:
        widget = render_dialog(node, child_widgets=child_widgets, theme_variant=theme_variant)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.SLIDER:
        if _should_suppress_playback_slider_node(node, parent_node):
            return _finalize_widget(
                node,
                "const SizedBox.shrink()",
                parent_type=parent_type,
                scroll_content_root=scroll_content_root,
            )
        widget = render_slider(node, theme_variant=theme_variant)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.CONTAINER and layout_fact_checkbox_control(node):
        from figma_flutter_agent.generator.layout.flex_policy.stack import (
            layout_fact_icon_badge_stack,
        )

        if parent_node is None or not layout_fact_icon_badge_stack(parent_node):
            widget = render_checkbox(node, theme_variant=theme_variant)
            width = node.sizing.width
            height = node.sizing.height
            if width is not None and height is not None and width > 0 and height > 0:
                widget = f"SizedBox(width: {width}, height: {height}, child: {widget})"
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )

    return None


def card_should_emit_as_overlay_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when card children are absolutely layered rather than flow-stacked."""
    if node.type != NodeType.CARD:
        return False
    placed = [child for child in node.children if child.stack_placement is not None]
    if len(placed) < 2:
        return False
    origins = {
        (
            round(float(child.stack_placement.left or 0.0), 1),
            round(float(child.stack_placement.top or 0.0), 1),
        )
        for child in placed
        if child.stack_placement is not None
    }
    return len(origins) >= 2


def render_card(node: CleanDesignTreeNode, ctx: dict[str, Any], flow: dict[str, Any]) -> str:
    """Render a NodeType.CARD node."""
    from figma_flutter_agent.generator.cluster_variants import resolve_cluster_delegate_class
    from figma_flutter_agent.parser.interaction.icons import passive_decorative_icon_glyph

    def _ctx_get(key: str, default: object = None) -> object:
        if hasattr(ctx, key):
            return getattr(ctx, key)
        if isinstance(ctx, dict):
            return ctx.get(key, default)
        return default

    if passive_decorative_icon_glyph(node):
        uses_svg = bool(_ctx_get("uses_svg"))
        cluster_classes = _ctx_get("cluster_classes")
        from figma_flutter_agent.generator.cluster_variants import primary_vector_asset

        delegate_class = resolve_cluster_delegate_class(
            node,
            cluster_classes,
            skip_cluster_id=_ctx_get("skip_cluster_id"),
        )
        parent_type = flow["parent_type"]
        parent_node = flow["parent_node"]
        scroll_content_root = flow["scroll_content_root"]
        if delegate_class is not None:
            return _finalize_widget(
                node,
                f"const {delegate_class}()",
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
        export_node = node
        subtree_asset = primary_vector_asset(node)
        if subtree_asset and not node.vector_asset_key:
            export_node = node.model_copy(update={"vector_asset_key": subtree_asset})
        exported = _render_exported_vector(export_node, uses_svg=uses_svg)
        if exported is not None:
            return _finalize_widget(
                node,
                exported,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )

    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    scroll_content_root = flow["scroll_content_root"]
    child_widgets = flow["child_widgets"]
    cross_axis = flow["cross_axis"]

    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_card_compact_radio_header,
    )

    if layout_fact_card_compact_radio_header(node):
        from figma_flutter_agent.generator.layout import render_node_body
        from figma_flutter_agent.generator.layout.form import render_radio

        theme_variant = ctx["theme_variant"]
        uses_svg = ctx["uses_svg"]
        if len(node.children) == 1 and node.children[0].type == NodeType.COLUMN:
            column = node.children[0]
            radio_child = next(
                (child for child in column.children if child.type == NodeType.RADIO),
                None,
            )
            text_child = next(
                (child for child in column.children if child.type == NodeType.TEXT),
                None,
            )
            radio_widget = (
                render_radio(
                    radio_child,
                    theme_variant=theme_variant,
                    parent_node=column,
                    ancestor_hosts=(node, column),
                )
                if radio_child is not None
                else "const SizedBox.shrink()"
            )
            label_widget = (
                render_node_body(
                    text_child,
                    uses_svg=uses_svg,
                    theme_variant=theme_variant,
                    parent_type=NodeType.COLUMN,
                    parent_node=column,
                )
                if text_child is not None
                else "const SizedBox.shrink()"
            )
            gap = format_geometry_literal(float(column.spacing or node.spacing or 8.0))
            widget = (
                "Row(mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.center, "
                f"children: [{radio_widget}, SizedBox(width: {gap}), {label_widget}])"
            )
        else:
            parts: list[str] = []
            for child, widget in zip(node.children, child_widgets, strict=True):
                if child.type == NodeType.RADIO:
                    parts.append(
                        render_radio(
                            child,
                            theme_variant=theme_variant,
                            parent_node=node,
                            ancestor_hosts=(node,),
                        )
                    )
                else:
                    parts.append(widget)
            gap = format_geometry_literal(float(node.spacing or 8.0))
            widget = (
                f"Row(mainAxisSize: MainAxisSize.min, "
                f"crossAxisAlignment: CrossAxisAlignment.center, "
                f"children: [{parts[0]}, SizedBox(width: {gap}), {parts[1]}])"
                if len(parts) >= 2
                else ", ".join(parts)
            )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    from figma_flutter_agent.generator.layout.flex_policy import (
        card_has_edge_to_edge_hero_stack,
        card_has_inset_hero_media_frame,
    )
    from figma_flutter_agent.generator.layout.scroll import padding_edge_insets

    elevation = card_elevation_expr(node.style)
    radius = border_radius_expr(node.style)
    if card_should_emit_as_overlay_stack(node):
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        width = node.sizing.width
        height = node.sizing.height
        width_lit = (
            format_geometry_literal(width) if width is not None and width > 0 else "double.infinity"
        )
        height_lit = (
            format_geometry_literal(height)
            if height is not None and height > 0
            else "double.infinity"
        )
        widget = (
            f"SizedBox(width: {width_lit}, height: {height_lit}, "
            f"child: Stack(clipBehavior: Clip.none, children: [{body}]))"
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if card_has_edge_to_edge_hero_stack(node) and len(child_widgets) >= 2:
        hero_widget = child_widgets[0]
        meta_body = ", ".join(child_widgets[1:]) or "const SizedBox.shrink()"
        hero = node.children[0]
        hero_width = hero.sizing.width
        hero_height = hero.sizing.height
        if (
            hero_width is not None
            and hero_height is not None
            and float(hero_width) > 0
            and float(hero_height) > 0
        ):
            if card_has_inset_hero_media_frame(node):
                hero_w_lit = format_geometry_literal(float(hero_width))
                hero_h_lit = format_geometry_literal(float(hero_height))
                hero_radius = hero.style.border_radius
                hero_radius_lit = format_geometry_literal(
                    float(hero_radius)
                    if hero_radius is not None and float(hero_radius) > 0
                    else 0.0
                )
                hero_slot = (
                    f"SizedBox(width: {hero_w_lit}, height: {hero_h_lit}, "
                    f"child: ClipRRect("
                    f"borderRadius: BorderRadius.circular({hero_radius_lit}), "
                    f"child: {hero_widget}))"
                )
                column_widget = (
                    "Column("
                    "mainAxisSize: MainAxisSize.min, "
                    f"crossAxisAlignment: {cross_axis}, "
                    f"children: [{hero_slot}, {meta_body}]"
                    ")"
                )
                card_padding = padding_edge_insets(node)
                if card_padding is not None:
                    column_widget = f"Padding(padding: {card_padding}, child: {column_widget})"
                card_width = node.sizing.width
                card_height = node.sizing.height
                width_lit = (
                    format_geometry_literal(float(card_width))
                    if card_width is not None and float(card_width) > 0
                    else "double.infinity"
                )
                height_lit = (
                    format_geometry_literal(float(card_height))
                    if card_height is not None and float(card_height) > 0
                    else "double.infinity"
                )
                if card_emit_needs_material_shell(node.style):
                    shell_color = (
                        f"color: {dart_color_expr(node.style)}, "
                        if node.style.background_color
                        else "color: Colors.transparent, "
                    )
                    widget = (
                        f"Material("
                        f"elevation: {elevation}, "
                        f"{shell_color}"
                        f"borderRadius: {radius}, "
                        "clipBehavior: Clip.antiAlias, "
                        f"child: {column_widget}"
                        "))"
                    )
                else:
                    widget = (
                        f"SizedBox(width: {width_lit}, height: {height_lit}, "
                        f"child: {column_widget})"
                    )
            else:
                top_radius = format_geometry_literal(float(node.style.border_radius or 22.0))
                hero_aspect = format_geometry_literal(float(hero_width) / float(hero_height))
                hero_slot = (
                    f"ClipRRect("
                    f"borderRadius: BorderRadius.vertical("
                    f"top: Radius.circular({top_radius})), "
                    f"child: AspectRatio(aspectRatio: {hero_aspect}, child: {hero_widget}))"
                )
                widget = (
                    f"Material("
                    f"elevation: {elevation}, "
                    f"borderRadius: {radius}, "
                    "clipBehavior: Clip.none, "
                    "child: Column("
                    "mainAxisSize: MainAxisSize.min, "
                    f"crossAxisAlignment: {cross_axis}, "
                    f"children: [{hero_slot}, {meta_body}]"
                    "))"
                )
        else:
            widget = (
                f"Material("
                f"elevation: {elevation}, "
                f"borderRadius: {radius}, "
                "clipBehavior: Clip.antiAlias, "
                f"child: Column("
                "mainAxisSize: MainAxisSize.min, "
                f"crossAxisAlignment: {cross_axis}, "
                f"children: [{hero_widget}, {meta_body}]"
                "))"
            )
    else:
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        decoration = box_decoration_expr(
            node.style,
            width=node.sizing.width,
            height=node.sizing.height,
        )
        if decoration is not None and node.style.effects:
            widget = f"Container(decoration: {decoration}, child: {body})"
        else:
            widget = (
                f"Card("
                f"elevation: {elevation}, "
                f"shape: RoundedRectangleBorder(borderRadius: {radius}), "
                f"child: Padding("
                f"padding: const EdgeInsets.all(AppSpacing.md), "
                f"child: Column(crossAxisAlignment: {cross_axis}, children: [{body}])"
                f")"
                f")"
            )
    return _finalize_widget(
        node,
        widget,
        parent_type=parent_type,
        parent_node=parent_node,
        scroll_content_root=scroll_content_root,
    )


def render_tabs_carousel_bottomnav_wrap(
    node: CleanDesignTreeNode, ctx: dict, flow: dict
) -> str | None:
    """Render TABS/CAROUSEL/BOTTOM_NAV/WRAP. Returns None if no branch matches."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    scroll_content_root = flow["scroll_content_root"]
    child_widgets = flow["child_widgets"]
    theme_variant = ctx["theme_variant"]
    uses_svg = ctx["uses_svg"]

    if node.type == NodeType.TABS:
        widget = render_tabs(child_widgets, node, theme_variant=theme_variant)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.CAROUSEL:
        widget = render_carousel(child_widgets, node, parent_type=parent_type)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.BOTTOM_NAV:
        from figma_flutter_agent.generator.layout.navigation.host import (
            compose_bottom_navigation_host,
        )

        widget = compose_bottom_navigation_host(
            node,
            uses_svg=uses_svg,
            theme_variant=theme_variant,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if node.type == NodeType.WRAP:
        from figma_flutter_agent.parser.semantics.signals.chip_anatomy import (
            is_static_segmented_number_row,
        )

        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        if is_static_segmented_number_row(node):
            widget = f"Row(mainAxisSize: MainAxisSize.min, children: [{body}])"
        else:
            spacing = format_geometry_literal(node.spacing)
            widget = f"Wrap(spacing: {spacing}, runSpacing: {spacing}, children: [{body}])"
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    return None


def render_grid(node: CleanDesignTreeNode, ctx: dict[str, Any], flow: dict[str, Any]) -> str:
    """Render a NodeType.GRID node."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    scroll_content_root = flow["scroll_content_root"]
    is_layout_root = flow["is_layout_root"]
    child_widgets = flow["child_widgets"]
    responsive_enabled = ctx["responsive_enabled"]
    design_artboard_width = ctx["design_artboard_width"]

    widget = render_grid_view(
        node,
        child_widgets,
        parent_type=parent_type,
        responsive_enabled=responsive_enabled,
        is_layout_root=is_layout_root,
        design_artboard_width=design_artboard_width,
    )
    return _finalize_widget(
        node,
        widget,
        parent_type=parent_type,
        parent_node=parent_node,
        scroll_content_root=scroll_content_root,
    )


class render_misc:
    """Namespace for one-off node renderers used directly by dispatch."""

    @staticmethod
    def list_tile_leading_icon(
        node: CleanDesignTreeNode,
        *,
        parent_node: CleanDesignTreeNode | None,
        uses_svg: bool,
        cluster_id: str | None,
        cluster_vector_variants: dict | None,
        parent_type: NodeType | None,
    ) -> str:
        icon_asset = node.vector_asset_key
        if icon_asset is None and cluster_id and cluster_vector_variants:
            variant = cluster_vector_variants.get(cluster_id)
            if variant is not None:
                icon_asset = variant.forward_asset
        width = node.sizing.width or 48.0
        height = node.sizing.height or 48.0
        background = (
            dart_color_expr(node.style)
            if node.style.background_color is not None
            else "Theme.of(context).colorScheme.surfaceContainerHighest"
        )
        radius = node.style.border_radius or 18.0
        from figma_flutter_agent.generator.layout.widgets.button.core import (
            render_compact_icon_host_stack_body,
        )

        layered_stack = render_compact_icon_host_stack_body(node, uses_svg=uses_svg)
        if layered_stack is not None:
            glyph = layered_stack
        elif icon_asset is not None and uses_svg:
            glyph = _render_svg_picture(node, escape_dart_string(icon_asset))
        elif node.type == NodeType.BUTTON and layout_fact_compact_icon_action_button(node):
            glyph = _find_icon_glyph_expr(node) or "const SizedBox.shrink()"
        elif parent_node is not None and len(parent_node.children) > 1:
            from figma_flutter_agent.generator.layout.navigation.items import nav_icon_expr

            title_host = parent_node.children[1]
            glyph = nav_icon_expr(title_host, uses_svg=False)
        else:
            glyph = "const SizedBox.shrink()"
        return (
            f"Container(width: {format_geometry_literal(width)}, "
            f"height: {format_geometry_literal(height)}, "
            f"decoration: BoxDecoration(color: {background}, "
            f"borderRadius: BorderRadius.circular({format_geometry_literal(radius)})), "
            "child: Row(mainAxisAlignment: MainAxisAlignment.center, "
            f"crossAxisAlignment: CrossAxisAlignment.center, children: [{glyph}]))"
        )

    @staticmethod
    def image_asset_leaf(
        node: CleanDesignTreeNode, ctx: dict[str, Any], flow: dict[str, Any]
    ) -> str | None:
        parent_type = flow["parent_type"]
        parent_node = flow["parent_node"]
        scroll_content_root = flow["scroll_content_root"]
        uses_svg = ctx["uses_svg"]

        exported = _render_exported_vector(node, uses_svg=uses_svg)
        if exported is None:
            return None
        fill_parent = _should_center_in_parent_stack_local(node, parent_node)
        widget = exported
        if fill_parent:
            widget = _wrap_centered_stack_child_local(node, widget)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
        )

    @staticmethod
    def fallback(node: CleanDesignTreeNode, ctx: dict[str, Any], flow: dict[str, Any]) -> str:
        parent_type = flow["parent_type"]
        parent_node = flow["parent_node"]
        scroll_content_root = flow["scroll_content_root"]
        child_widgets = flow["child_widgets"]
        cross_axis = flow["cross_axis"]
        uses_svg = ctx["uses_svg"]

        if child_widgets:
            body = ", ".join(child_widgets)
            inner = f"Column(crossAxisAlignment: {cross_axis}, children: [{body}])"
            box_decoration = box_decoration_expr(
                node.style,
                width=node.sizing.width,
                height=node.sizing.height,
            )
            if box_decoration is not None and node.type in {
                NodeType.CONTAINER,
                NodeType.COLUMN,
                NodeType.ROW,
            }:
                inner = f"Container(decoration: {box_decoration}, child: {inner})"
            return _finalize_widget(
                node, inner, parent_type=parent_type, scroll_content_root=scroll_content_root
            )

        if uses_svg and _should_prefer_exported_svg(node):
            exported = _render_exported_vector(node, uses_svg=uses_svg)
            if exported is not None:
                return _finalize_widget(
                    node,
                    exported,
                    parent_type=parent_type,
                    parent_node=parent_node,
                    scroll_content_root=scroll_content_root,
                )
            if node.vector_svg_has_filter or node.image_asset_key:
                from figma_flutter_agent.generator.layout.widgets.emit import media as emit_media

                media_widget = emit_media.render_image_or_vector(node, ctx, flow)
                if media_widget is not None:
                    return media_widget

        leaf_surface = _render_leaf_surface(node)
        if leaf_surface is not None:
            return _finalize_widget(
                node, leaf_surface, parent_type=parent_type, scroll_content_root=scroll_content_root
            )

        glyph = _render_stroke_glyph_fallback(node)
        if glyph is not None:
            return _finalize_widget(
                node, glyph, parent_type=parent_type, scroll_content_root=scroll_content_root
            )

        from figma_flutter_agent.generator.layout.spacer import dimensioned_spacer_widget_expr

        spacer = dimensioned_spacer_widget_expr(node)
        if spacer is not None:
            return _finalize_widget(
                node,
                spacer,
                parent_type=parent_type,
                scroll_content_root=scroll_content_root,
            )

        return _finalize_widget(
            node,
            "const SizedBox.shrink()",
            parent_type=parent_type,
            scroll_content_root=scroll_content_root,
        )


from ..svg import (
    _should_center_in_parent_stack as _should_center_in_parent_stack_local,  # noqa: E402
)
from ..svg import _wrap_centered_stack_child as _wrap_centered_stack_child_local  # noqa: E402
