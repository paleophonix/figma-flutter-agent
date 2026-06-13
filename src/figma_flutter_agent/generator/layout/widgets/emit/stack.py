"""STACK rendering branch and the logo-wordmark stack archetype."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_back_nav_stack as cupertino_wrap_back_nav_stack,
)
from figma_flutter_agent.generator.layout.style import box_decoration_expr
from figma_flutter_agent.parser.interaction import (
    is_back_navigation_icon_stack,
    looks_like_back_nav_stack,
    looks_like_skip_control_stack,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.parser.render_bounds import stack_needs_soft_clip
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..button import _wrap_button_stack
from ..finalize import _finalize_widget
from ..hero import try_render_product_recommendation_hero_stack
from ..input import _render_stack_input
from ..playback import (
    _try_render_play_pause_stack,
    _try_render_pruned_cluster_skip_control,
)
from ..position import _wrap_root_stack_viewport
from ..thumbnail import try_render_square_product_photo_stack


def _stack_child_left(child: CleanDesignTreeNode) -> float:
    if child.stack_placement is not None and child.stack_placement.left is not None:
        return float(child.stack_placement.left)
    return float(child.offset_x)


def _is_logo_wordmark_stack(node: CleanDesignTreeNode) -> bool:
    if node.type != NodeType.STACK or len(node.children) != 3:
        return False
    texts = [child for child in node.children if child.type == NodeType.TEXT]
    if len(texts) != 2:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if node.stack_placement is not None:
        if node.stack_placement.width is not None:
            width = node.stack_placement.width
        if node.stack_placement.height is not None:
            height = node.stack_placement.height
    return (
        width is not None and height is not None and width <= 220.0 and height <= 48.0
    )


def _logo_wordmark_stack_size(node: CleanDesignTreeNode) -> tuple[float, float]:
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    if node.stack_placement is not None:
        if node.stack_placement.width is not None:
            width = float(node.stack_placement.width)
        if node.stack_placement.height is not None:
            height = float(node.stack_placement.height)
    return width, height


def _render_logo_wordmark_stack(node: CleanDesignTreeNode, ctx: dict, *, recurse) -> str:
    width, height = _logo_wordmark_stack_size(node)
    child_widgets = [
        recurse(
            child,
            uses_svg=ctx["uses_svg"],
            parent_type=NodeType.STACK,
            parent_node=node,
            theme_variant=ctx["theme_variant"],
            cluster_classes=ctx["cluster_classes"],
            cluster_vector_variants=ctx["cluster_vector_variants"],
            cluster_vector_variant=ctx["cluster_vector_variant"],
            skip_cluster_id=ctx["skip_cluster_id"],
            responsive_enabled=ctx["responsive_enabled"],
            design_artboard_width=ctx["design_artboard_width"],
            bundled_font_families=ctx["bundled_font_families"],
            dart_weight_overrides_by_family=ctx["dart_weight_overrides_by_family"],
            text_theme_slot_by_style_name=ctx["text_theme_slot_by_style_name"],
            text_theme_size_slots=ctx["text_theme_size_slots"],
        )
        for child in sorted(node.children, key=_stack_child_left)
    ]
    return (
        f"SizedBox("
        f"width: {format_geometry_literal(width)}, "
        f"height: {format_geometry_literal(height)}, "
        f"child: Stack(clipBehavior: Clip.none, children: [{', '.join(child_widgets)}])"
        ")"
    )


def render_stack(node: CleanDesignTreeNode, ctx: dict, flow: dict, *, recurse) -> str:
    """Render a NodeType.STACK node (the non-early-return path)."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    is_layout_root = flow["is_layout_root"]
    scroll_content_root = flow["scroll_content_root"]
    child_widgets = flow["child_widgets"]
    sorted_children = flow["sorted_children"]
    metadata_column_host = flow["metadata_column_host"]
    paired_circle_ids = flow["paired_circle_ids"]
    omit_child_ids = flow["omit_child_ids"]
    playback_seek_ids = flow["playback_seek_ids"]
    playback_decor_omit_ids = flow["playback_decor_omit_ids"]
    playback_seek_widget = flow["playback_seek_widget"]
    uses_svg = ctx["uses_svg"]
    theme_variant = ctx["theme_variant"]
    skip_cluster_id = ctx["skip_cluster_id"]
    cluster_vector_variant = ctx["cluster_vector_variant"]
    responsive_enabled = ctx["responsive_enabled"]
    bundled_font_families = ctx["bundled_font_families"]
    dart_weight_overrides_by_family = ctx["dart_weight_overrides_by_family"]
    text_theme_slot_by_style_name = ctx["text_theme_slot_by_style_name"]
    text_theme_size_slots = ctx["text_theme_size_slots"]

    from figma_flutter_agent.assets.composite_icons import (
        is_composite_icon_export_node,
    )
    from figma_flutter_agent.parser.interaction import is_device_system_chrome_node

    if is_device_system_chrome_node(node) and "home indicator" in (node.name or "").lower():
        from figma_flutter_agent.generator.layout.stack_chrome import (
            device_home_indicator_bar_expr,
        )

        height = node.sizing.height
        widget = device_home_indicator_bar_expr(
            float(height) if height is not None else None
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    from ..svg import (
        _render_svg_picture,
        _should_center_in_parent_stack,
        _wrap_centered_stack_child,
    )

    if uses_svg and is_composite_icon_export_node(node) and node.vector_asset_key:
        widget = _render_svg_picture(
            node,
            escape_dart_string(node.vector_asset_key),
        )
        fill_parent = _should_center_in_parent_stack(node, parent_node)
        if fill_parent:
            widget = _wrap_centered_stack_child(node, widget)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
        )
    play_pause = _try_render_play_pause_stack(node)
    if play_pause is not None:
        label = escape_dart_string(node.accessibility_label or node.name)
        play_pause = _wrap_button_stack(
            play_pause, node, theme_variant=theme_variant
        )
        play_pause = f"Semantics(label: '{label}', child: {play_pause})"
        return _finalize_widget(node, play_pause, parent_type=parent_type, scroll_content_root=scroll_content_root)
    photo_stack = try_render_product_recommendation_hero_stack(
        node,
        uses_svg=uses_svg,
        render_node_body=recurse,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if photo_stack is None:
        photo_stack = try_render_square_product_photo_stack(
            node,
            parent_node=parent_node,
            uses_svg=uses_svg,
            render_node_body=recurse,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    if photo_stack is not None:
        return _finalize_widget(
            node,
            photo_stack,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    from figma_flutter_agent.generator.layout.widgets.stepper import (
        render_compact_quantity_stepper_stack,
    )
    from figma_flutter_agent.parser.interaction import stack_is_compact_quantity_stepper

    if stack_is_compact_quantity_stepper(node):
        compact_stepper = render_compact_quantity_stepper_stack(node)
        if compact_stepper is not None:
            return _finalize_widget(
                node,
                compact_stepper,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
    pruned_skip = _try_render_pruned_cluster_skip_control(
        node,
        uses_svg=uses_svg,
        skip_cluster_id=skip_cluster_id,
        cluster_vector_variant=cluster_vector_variant,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if pruned_skip is not None:
        label = escape_dart_string(node.accessibility_label or node.name)
        pruned_skip = f"Semantics(label: '{label}', child: {pruned_skip})"
        return _finalize_widget(node, pruned_skip, parent_type=parent_type, scroll_content_root=scroll_content_root)
    if not is_layout_root and looks_like_back_nav_stack(node):
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        stack_widget = f"Stack(clipBehavior: Clip.none, children: [{body}])"
        if is_back_navigation_icon_stack(node):
            stack_widget = cupertino_wrap_back_nav_stack(
                stack_widget,
                theme_variant=theme_variant,
                node_id=node.id,
            )
        else:
            stack_widget = _wrap_button_stack(
                stack_widget,
                node,
                theme_variant=theme_variant,
            )
        return _finalize_widget(
            node,
            stack_widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if not is_layout_root and looks_like_skip_control_stack(node):
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        stack_widget = f"Stack(clipBehavior: Clip.none, children: [{body}])"
        label = escape_dart_string(node.accessibility_label or node.name)
        stack_widget = _wrap_button_stack(
            stack_widget,
            node,
            theme_variant=theme_variant,
        )
        stack_widget = f"Semantics(label: '{label}', child: {stack_widget})"
        return _finalize_widget(
            node,
            stack_widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    interaction = None if is_layout_root else stack_interaction_kind(node)
    if interaction == "input":
        return _render_stack_input(
            node,
            theme_variant=theme_variant,
            parent_type=parent_type,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    stack_children = list(child_widgets)
    if playback_seek_widget is not None:
        stack_children.append(playback_seek_widget)
    body = ", ".join(stack_children) or "const SizedBox.shrink()"
    from figma_flutter_agent.generator.layout.flex_policy import (
        column_center_hug_child_wrap,
        column_child_should_center_hug,
        stack_child_ordinal_bottom,
        stack_child_ordinal_left,
        stack_child_ordinal_top,
        stack_flow_child_horizontal_wrap,
        stack_flow_child_vertical_extent_wrap,
        stack_pill_button_wrap_spacing,
        stack_should_flow_as_centered_wrap,
        stack_should_flow_as_column,
    )

    from figma_flutter_agent.generator.layout.stack_chrome import (
        emit_viewport_device_chrome_sandwich_column,
        stack_is_viewport_device_chrome_sandwich,
    )

    if stack_is_viewport_device_chrome_sandwich(node):
        ordered_pairs = sorted(
            zip(sorted_children, stack_children, strict=True),
            key=lambda pair: (stack_child_ordinal_top(pair[0]), pair[0].id),
        )
        stack_widget = emit_viewport_device_chrome_sandwich_column(
            node,
            [pair[0] for pair in ordered_pairs],
            [pair[1] for pair in ordered_pairs],
        )
    elif stack_should_flow_as_centered_wrap(node):
        ordered_pairs = sorted(
            zip(sorted_children, stack_children, strict=True),
            key=lambda pair: (
                stack_child_ordinal_top(pair[0]),
                stack_child_ordinal_left(pair[0]),
                pair[0].id,
            ),
        )
        spacing_lit = format_geometry_literal(
            stack_pill_button_wrap_spacing(node.children)
        )
        flow_parts = [widget for _, widget in ordered_pairs]
        body = ", ".join(flow_parts) or "const SizedBox.shrink()"
        stack_widget = (
            "Wrap("
            "alignment: WrapAlignment.start, "
            "runAlignment: WrapAlignment.start, "
            f"spacing: {spacing_lit}, "
            f"runSpacing: {spacing_lit}, "
            f"children: [{body}]"
            ")"
        )
    elif stack_should_flow_as_column(node):
        ordered_pairs = sorted(
            zip(sorted_children, stack_children, strict=True),
            key=lambda pair: (stack_child_ordinal_top(pair[0]), pair[0].id),
        )
        flow_parts: list[str] = []
        for index, (child, widget) in enumerate(ordered_pairs):
            if index > 0:
                previous_child = ordered_pairs[index - 1][0]
                gap = stack_child_ordinal_top(child) - stack_child_ordinal_bottom(
                    previous_child
                )
                if gap > 0.5:
                    flow_parts.append(
                        f"SizedBox(height: {format_geometry_literal(gap)})"
                    )
            flow_widget = stack_flow_child_horizontal_wrap(child, widget)
            flow_widget = stack_flow_child_vertical_extent_wrap(
                child, flow_widget, parent_node=node
            )
            if column_child_should_center_hug(node, child):
                flow_widget = column_center_hug_child_wrap(node, child, flow_widget)
            flow_parts.append(flow_widget)
        body = ", ".join(flow_parts) or "const SizedBox.shrink()"
        stack_widget = (
            "Column("
            "mainAxisSize: MainAxisSize.min, "
            "crossAxisAlignment: CrossAxisAlignment.stretch, "
            f"children: [{body}]"
            ")"
        )
    elif metadata_column_host:
        spacing_field = ""
        if len(stack_children) >= 2:
            from figma_flutter_agent.generator.layout.flex_policy import (
                stack_child_ordinal_top,
            )

            ordered = sorted(
                node.children,
                key=lambda child: (stack_child_ordinal_top(child), child.id),
            )
            if len(ordered) >= 2:
                first = ordered[0]
                second = ordered[1]
                first_height = first.sizing.height or 0.0
                gap = stack_child_ordinal_top(second) - (
                    stack_child_ordinal_top(first) + first_height
                )
                if gap > 0:
                    spacing_field = (
                        f"spacing: {format_geometry_literal(gap)}, "
                    )
        stack_widget = (
            "Column("
            "mainAxisSize: MainAxisSize.min, "
            "crossAxisAlignment: CrossAxisAlignment.end, "
            f"{spacing_field}"
            f"children: [{body}]"
            ")"
        )
    else:
        from figma_flutter_agent.generator.layout.stack_chrome import (
            apply_pin_bottom_chrome_to_stack_layers,
        )

        stack_emit_children = [
            child
            for child in sorted_children
            if child.id not in paired_circle_ids
            and child.id not in omit_child_ids
            and child.id not in playback_seek_ids
            and child.id not in playback_decor_omit_ids
        ]
        if len(stack_emit_children) == len(stack_children):
            stack_children = apply_pin_bottom_chrome_to_stack_layers(
                node,
                stack_emit_children,
                stack_children,
                allow_outward_paint=stack_needs_soft_clip(node),
            )
            body = ", ".join(stack_children) or "const SizedBox.shrink()"
        stack_clip = (
            "Clip.none"
            if not is_layout_root or stack_needs_soft_clip(node)
            else "Clip.hardEdge"
        )
        stack_widget = f"Stack(clipBehavior: {stack_clip}, children: [{body}])"
    if interaction == "button":
        if len(child_widgets) == 1 and "InkWell(" in child_widgets[0]:
            stack_widget = child_widgets[0]
        else:
            stack_widget = _wrap_button_stack(
                stack_widget, node, theme_variant=theme_variant
            )
    root_decoration = (
        box_decoration_expr(
            node.style,
            width=node.sizing.width,
            height=node.sizing.height,
        )
        if is_layout_root
        else None
    )
    if root_decoration is not None:
        stack_widget = (
            f"Container(decoration: {root_decoration}, child: {stack_widget})"
        )
    stack_widget = _wrap_root_stack_viewport(
        node,
        stack_widget,
        is_layout_root=is_layout_root,
        responsive_enabled=responsive_enabled,
        theme_variant=theme_variant,
    )
    return _finalize_widget(
        node,
        stack_widget,
        parent_type=parent_type,
        parent_node=parent_node,
        scroll_content_root=scroll_content_root,
    )
