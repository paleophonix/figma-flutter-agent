"""Top-level recursive dispatcher: render_node_body."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (  # noqa: F401
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.parser.interaction import (
    layout_fact_textarea_field,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..button import _try_render_consent_checkbox_row
from ..finalize import _finalize_widget, _wrap_render_boundary_tap
from ..input import _render_textarea_field
from ..playback import (
    _sizing_like_skip_control,
    _try_render_pruned_cluster_skip_control,
)
from ..svg import (
    _render_exported_vector,
    _should_center_in_parent_stack,
    _wrap_centered_stack_child,
)
from .containers import render_misc
from .helpers import (
    _try_render_early_stack_special_case,
    _try_render_non_root_stack_special_case,
)
from .shell import assemble_layout_emit, build_render_ctx
from .stack import (
    _is_logo_wordmark_stack,
    _is_vector_logo_mark_stack,
    _render_logo_wordmark_stack,
    _render_vector_logo_mark_stack,
)


def render_node_body(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    parent_type: NodeType | None = None,
    parent_node: CleanDesignTreeNode | None = None,
    theme_variant: str = "material_3",
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
    cluster_vector_variant=None,
    skip_cluster_id: str | None = None,
    responsive_enabled: bool = False,
    is_layout_root: bool = False,
    design_artboard_width: float | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    de_archetype_pass: bool = False,
    ir_by_id: dict | None = None,
    scroll_content_root: bool = False,
) -> str:
    """Render a Dart widget expression for a clean-tree node."""
    ctx = build_render_ctx(
        uses_svg=uses_svg,
        theme_variant=theme_variant,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        cluster_vector_variant=cluster_vector_variant,
        skip_cluster_id=skip_cluster_id,
        responsive_enabled=responsive_enabled,
        design_artboard_width=design_artboard_width,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        de_archetype_pass=de_archetype_pass,
        ir_by_id=ir_by_id,
    )
    recurse = render_node_body

    from figma_flutter_agent.generator.layout.interactive_weekday import render_weekday_chip_row
    from figma_flutter_agent.parser.interaction import layout_fact_compact_chip_row

    if layout_fact_compact_chip_row(node) and not is_layout_root:
        return _finalize_widget(
            node,
            render_weekday_chip_row(node),
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if not de_archetype_pass and _is_logo_wordmark_stack(node):
        return _finalize_widget(
            node,
            _render_logo_wordmark_stack(node, ctx, recurse=recurse),
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if not de_archetype_pass and _is_vector_logo_mark_stack(node):
        return _finalize_widget(
            node,
            _render_vector_logo_mark_stack(node, ctx, recurse=recurse),
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if not de_archetype_pass:
        consent_row = _try_render_consent_checkbox_row(
            node,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if consent_row is not None:
            return _finalize_widget(
                node,
                consent_row,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )

    if node.type == NodeType.STACK and not is_layout_root:
        non_root_stack_widget = _try_render_non_root_stack_special_case(
            node, ctx, de_archetype_pass=de_archetype_pass
        )
        if non_root_stack_widget is not None:
            return _finalize_widget(
                node,
                non_root_stack_widget,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )

    if not de_archetype_pass:
        from figma_flutter_agent.generator.layout.widgets.option_chip import (
            try_emit_chip_choice_layout_for_node,
        )

        cluster_delegated = (
            node.cluster_id is not None
            and cluster_classes is not None
            and node.cluster_id in cluster_classes
        )
        if not cluster_delegated:
            chip_choice_body = try_emit_chip_choice_layout_for_node(node, ctx)
            if chip_choice_body is not None:
                return _finalize_widget(
                    node,
                    chip_choice_body,
                    parent_type=parent_type,
                    parent_node=parent_node,
                    scroll_content_root=scroll_content_root,
                )

    if layout_fact_textarea_field(node):
        return _render_textarea_field(
            node,
            theme_variant=theme_variant,
            parent_type=parent_type,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )

    if node.type == NodeType.COLUMN:
        from ..input.inline_hosts import try_render_inline_input_field_host

        inline_input = try_render_inline_input_field_host(
            node,
            theme_variant=theme_variant,
            parent_type=parent_type,
            uses_svg=uses_svg,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if inline_input is not None:
            return inline_input

    if node.type == NodeType.STACK:
        from figma_flutter_agent.generator.layout.flex_policy.stack import (
            layout_fact_icon_badge_stack,
        )
        from figma_flutter_agent.parser.interaction import layout_fact_stack_category_component_tile

        from ..svg import stack_should_emit_flattened_vector_group

        if (
            uses_svg
            and node.vector_asset_key
            and node.vector_asset_key.endswith(".svg")
            and stack_should_emit_flattened_vector_group(node)
            and not layout_fact_stack_category_component_tile(node)
            and not layout_fact_icon_badge_stack(node)
        ):
            exported = _render_exported_vector(node, uses_svg=uses_svg)
            if exported is not None:
                fill_parent = _should_center_in_parent_stack(node, parent_node)
                widget = exported
                from figma_flutter_agent.generator.layout.cupertino import wrap_back_nav_stack
                from figma_flutter_agent.parser.interaction import (
                    is_back_navigation_icon_stack,
                    layout_fact_compact_icon_action_stack,
                )
                from figma_flutter_agent.parser.numeric_rounding import (
                    format_geometry_literal as fmt_dim,
                )

                if layout_fact_compact_icon_action_stack(node) and is_back_navigation_icon_stack(
                    node
                ):
                    width = node.sizing.width
                    height = node.sizing.height
                    if (
                        width is not None
                        and height is not None
                        and float(width) > 0
                        and float(height) > 0
                    ):
                        widget = (
                            f"SizedBox("
                            f"width: {fmt_dim(float(width))}, "
                            f"height: {fmt_dim(float(height))}, "
                            f"child: {widget})"
                        )
                    stack_body = (
                        "Stack(clipBehavior: Clip.none, alignment: Alignment.center, "
                        f"children: [{widget}])"
                    )
                    widget = wrap_back_nav_stack(
                        stack_body,
                        theme_variant=theme_variant,
                        node_id=node.id,
                    )
                if fill_parent:
                    widget = _wrap_centered_stack_child(node, widget)
                return _finalize_widget(
                    node,
                    widget,
                    parent_type=parent_type,
                    parent_node=parent_node,
                    fill_parent=fill_parent,
                    scroll_content_root=scroll_content_root,
                )

    if node.type == NodeType.STACK:
        early_stack_result = _try_render_early_stack_special_case(
            node,
            ctx,
            de_archetype_pass=de_archetype_pass,
            parent_node=parent_node,
            recurse=recurse,
        )
        if early_stack_result is not None:
            early_stack_widget, use_parent_node = early_stack_result
            return _finalize_widget(
                node,
                early_stack_widget,
                parent_type=parent_type,
                parent_node=parent_node if use_parent_node else None,
                scroll_content_root=scroll_content_root,
            )

    from figma_flutter_agent.parser.interaction import layout_fact_stack_category_component_tile

    if (
        node.render_boundary
        and node.vector_asset_key
        and not layout_fact_stack_category_component_tile(node)
    ):
        from figma_flutter_agent.generator.cluster_variants import (
            resolve_cluster_delegate_class,
        )
        from figma_flutter_agent.generator.layout.flex_policy.stack import (
            layout_fact_icon_badge_stack,
        )

        delegate_class = resolve_cluster_delegate_class(
            node,
            cluster_classes,
            skip_cluster_id=skip_cluster_id,
        )
        cluster_delegate_pending = delegate_class is not None
        if not cluster_delegate_pending and not layout_fact_icon_badge_stack(node):
            from figma_flutter_agent.parser.interaction import find_raster_photo_leaf

            if find_raster_photo_leaf(node) is None:
                exported = _render_exported_vector(node, uses_svg=uses_svg)
                if exported is not None:
                    fill_parent = _should_center_in_parent_stack(node, parent_node)
                    widget = _wrap_render_boundary_tap(node, exported)
                    if fill_parent:
                        widget = _wrap_centered_stack_child(node, widget)
                    return _finalize_widget(
                        node,
                        widget,
                        parent_type=parent_type,
                        parent_node=parent_node,
                        fill_parent=fill_parent,
                        scroll_content_root=scroll_content_root,
                    )
                if node.vector_svg_has_filter or node.image_asset_key:
                    flow = {
                        "parent_type": parent_type,
                        "parent_node": parent_node,
                        "scroll_content_root": scroll_content_root,
                    }
                    ctx = {
                        "uses_svg": uses_svg,
                        "cluster_vector_variant": cluster_vector_variants.get(node.cluster_id)
                        if cluster_vector_variants and node.cluster_id
                        else None,
                    }
                    from figma_flutter_agent.generator.layout.widgets.emit import (
                        media as emit_media,
                    )

                    media_widget = emit_media.render_image_or_vector(node, ctx, flow)
                    if media_widget is not None:
                        return media_widget

    if node.extracted_widget_ref:
        from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host

        if not must_inline_extracted_widget_host(node):
            ref_name = node.extracted_widget_ref.strip()
            widget_expr = f"const {ref_name}()" if ref_name else "const SizedBox.shrink()"
            return _finalize_widget(
                node,
                widget_expr,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )

    cluster_id = node.cluster_id
    from figma_flutter_agent.parser.interaction import list_tile_leading_icon_slot

    if list_tile_leading_icon_slot(node, parent_node, parent_type=parent_type):
        widget = render_misc.list_tile_leading_icon(
            node,
            parent_node=parent_node,
            uses_svg=uses_svg,
            cluster_id=cluster_id,
            cluster_vector_variants=cluster_vector_variants,
            parent_type=parent_type,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    pruned_cluster_has_instance_asset = (
        cluster_id is not None
        and not node.children
        and bool(node.flatten_figma_node_ids)
        and bool(node.vector_asset_key)
    )
    from figma_flutter_agent.generator.cluster_variants import (
        resolve_cluster_delegate_class,
    )
    from figma_flutter_agent.parser.interaction import layout_fact_stack_category_component_tile

    has_cluster_delegate = (
        resolve_cluster_delegate_class(
            node,
            cluster_classes,
            skip_cluster_id=skip_cluster_id,
        )
        is not None
    )
    if (
        pruned_cluster_has_instance_asset
        and not has_cluster_delegate
        and not layout_fact_stack_category_component_tile(node)
    ):
        exported = _render_exported_vector(node, uses_svg=uses_svg)
        if exported is not None:
            from figma_flutter_agent.generator.layout.widgets import _node_layout_size

            width, height = _node_layout_size(node, node.stack_placement)
            widget = exported
            if width is not None and height is not None and width > 0 and height > 0:
                from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

                widget = (
                    f"SizedBox(width: {format_geometry_literal(float(width))}, "
                    f"height: {format_geometry_literal(float(height))}, child: {exported})"
                )
            label = escape_dart_string(node.accessibility_label or node.name or "Icon")
            return _finalize_widget(
                node,
                f"Semantics(label: '{label}', child: {widget})",
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
    from figma_flutter_agent.generator.layout.flex_policy import (
        layout_fact_row_numeric_counter_badge,
        layout_fact_row_status_pill_badge,
        layout_fact_row_tight_horizontal_pill_label,
    )
    from figma_flutter_agent.generator.layout.widgets.selection import (
        render_payment_selection_indicator,
    )
    from figma_flutter_agent.generator.variant.state import variant_is_checked
    from figma_flutter_agent.parser.interaction import (
        layout_fact_compact_icon_action_button,
        layout_fact_hosts_compact_checkbox_control,
        layout_fact_hosts_payment_selection_indicator,
    )

    if layout_fact_hosts_payment_selection_indicator(node):
        widget = render_payment_selection_indicator(
            node,
            selected=variant_is_checked(node),
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    from figma_flutter_agent.generator.cluster_variants import cluster_chip_reference_args
    from figma_flutter_agent.parser.interaction.chip_variant import is_tag_component_chip_row

    tag_option_chip = (
        is_tag_component_chip_row(node)
        and cluster_classes is not None
        and cluster_id is not None
        and cluster_id in cluster_classes
        and cluster_chip_reference_args(node) is not None
    )

    inline_cluster_control = (
        (layout_fact_row_tight_horizontal_pill_label(node) and not tag_option_chip)
        or layout_fact_row_status_pill_badge(node)
        or layout_fact_row_numeric_counter_badge(node)
        or layout_fact_hosts_compact_checkbox_control(node)
        or layout_fact_hosts_payment_selection_indicator(node)
        or (
            node.type == NodeType.BUTTON
            and layout_fact_compact_icon_action_button(node)
            and resolve_cluster_delegate_class(
                node,
                cluster_classes,
                skip_cluster_id=skip_cluster_id,
            )
            is None
        )
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_child_is_product_tile_metadata_slot,
    )
    from figma_flutter_agent.parser.interaction import layout_fact_stack_product_recommendation_hero

    product_tile_inline = layout_fact_stack_product_recommendation_hero(
        node
    ) or card_child_is_product_tile_metadata_slot(node, parent_node)

    delegate_class = resolve_cluster_delegate_class(
        node,
        cluster_classes,
        skip_cluster_id=skip_cluster_id,
    )
    prefer_cluster_widget = (
        not inline_cluster_control and not product_tile_inline and delegate_class is not None
    )
    if prefer_cluster_widget:
        from figma_flutter_agent.generator.cluster_variants import (
            cluster_chip_reference_args,
            cluster_reference_args,
        )
        from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host
        from figma_flutter_agent.parser.interaction.chip_variant import (
            is_tag_component_chip_row,
        )

        if must_inline_extracted_widget_host(node) or (
            cluster_chip_reference_args(node) is None and is_tag_component_chip_row(node)
        ):
            prefer_cluster_widget = False
        from figma_flutter_agent.parser.interaction.selection import (
            layout_fact_compact_trailing_selection_glyph,
        )
        from figma_flutter_agent.parser.interaction.step import (
            layout_fact_success_check_glyph_host,
        )

        if layout_fact_compact_trailing_selection_glyph(
            node
        ) or layout_fact_success_check_glyph_host(node):
            prefer_cluster_widget = False
    if prefer_cluster_widget:
        from figma_flutter_agent.generator.cluster_variants import (
            cluster_chip_reference_args,
            cluster_reference_args,
        )

        class_name = delegate_class
        variant = (
            cluster_vector_variants.get(cluster_id)
            if cluster_vector_variants and cluster_id
            else None
        )
        chip_args = cluster_chip_reference_args(node)
        if chip_args is not None:
            widget_expr = f"{class_name}({chip_args})"
            from figma_flutter_agent.generator.layout.widgets.option_chip import (
                wrap_tag_option_chip_reference,
            )

            widget_expr = wrap_tag_option_chip_reference(widget_expr, node)
            return _finalize_widget(
                node,
                widget_expr,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
        if variant is not None and _sizing_like_skip_control(node):
            args = cluster_reference_args(node, variant)
            widget_expr = f"const {class_name}({args})" if args else f"const {class_name}()"
            label = escape_dart_string(node.accessibility_label or node.name or class_name)
            return _finalize_widget(
                node,
                f"Semantics(label: '{label}', child: {widget_expr})",
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
        if variant is not None:
            args = cluster_reference_args(node, variant)
            if args:
                return _finalize_widget(
                    node,
                    f"{class_name}({args})",
                    parent_type=parent_type,
                    parent_node=parent_node,
                    scroll_content_root=scroll_content_root,
                )
        return _finalize_widget(
            node,
            f"const {class_name}()",
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    if (
        not de_archetype_pass
        and node.type == NodeType.STACK
        and not node.children
        and _sizing_like_skip_control(node)
    ):
        from figma_flutter_agent.parser.interaction import find_raster_photo_leaf

        if find_raster_photo_leaf(node) is None:
            variant = (
                cluster_vector_variants.get(node.cluster_id)
                if cluster_vector_variants and node.cluster_id
                else None
            )
            pruned = _try_render_pruned_cluster_skip_control(
                node,
                uses_svg=uses_svg,
                skip_cluster_id=skip_cluster_id,
                cluster_vector_variant=variant,
                theme_variant=theme_variant,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
            if pruned is not None:
                label = escape_dart_string(node.accessibility_label or node.name)
                return _finalize_widget(
                    node,
                    f"Semantics(label: '{label}', child: {pruned})",
                    parent_type=parent_type,
                    parent_node=parent_node,
                    scroll_content_root=scroll_content_root,
                )

    return assemble_layout_emit(
        node,
        ctx=ctx,
        recurse=recurse,
        parent_type=parent_type,
        parent_node=parent_node,
        is_layout_root=is_layout_root,
        scroll_content_root=scroll_content_root,
        uses_svg=uses_svg,
        theme_variant=theme_variant,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        cluster_vector_variant=cluster_vector_variant,
        skip_cluster_id=skip_cluster_id,
        responsive_enabled=responsive_enabled,
        design_artboard_width=design_artboard_width,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
