"""Layout shell emission with pre-built child widget expressions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from figma_flutter_agent.generator.layout.flex_policy import (
    resolve_cross_axis_alignment,
    resolve_main_axis_alignment,
    stack_child_ordinal_top,
)
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    stack_should_emit_as_metadata_column,
)
from figma_flutter_agent.parser.interaction import (
    primary_surface_node,
    stack_interaction_kind,
    surface_covers_node,
)
from figma_flutter_agent.parser.stack_paint import (
    sort_absolute_stack_children as _sort_absolute_stack_children,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..playback import (
    _find_concentric_circle_pair,
    _playback_seek_omit_child_ids,
    _playback_seek_vector_ids,
    _render_concentric_circle_thumb,
    _render_playback_seek_slider,
)
from .containers import (
    render_card,
    render_grid,
    render_misc,
    render_simple_controls,
    render_tabs_carousel_bottomnav_wrap,
)
from .context import LayoutRenderContext
from .controls import render_button_node, render_input_node
from .flex import render_column, render_row
from .media import render_image_or_vector
from .stack import render_stack
from .text import render_text_node

RecurseFn = Callable[..., str]


def build_render_ctx(
    *,
    uses_svg: bool,
    theme_variant: str,
    cluster_classes: dict[str, str] | None,
    cluster_vector_variants: dict | None,
    cluster_vector_variant: object,
    skip_cluster_id: str | None,
    responsive_enabled: bool,
    design_artboard_width: float | None,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
    de_archetype_pass: bool,
    ir_by_id: dict | None = None,
) -> LayoutRenderContext:
    """Build the shared render context for layout emitters."""
    return LayoutRenderContext(
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


def _button_covering_surface_may_omit(
    node: CleanDesignTreeNode,
    surface: CleanDesignTreeNode,
    sorted_children: list[CleanDesignTreeNode],
) -> bool:
    """Return True only when omitting a full-cover button surface is paint-safe.

    A covering background rectangle may be dropped from the child list only when
    its paint is transferred to the emitted host (Ink decoration) or the sole
    remaining child already spans the full host extent. When a smaller inner row
    survives omission, the surface must stay in the tree or be re-wrapped.
    """
    remaining = [child for child in sorted_children if child.id != surface.id]
    if len(remaining) == 1:
        inner = remaining[0]
        host_width = float(node.sizing.width or 0.0)
        host_height = float(node.sizing.height or 0.0)
        inner_width = float(inner.sizing.width or 0.0)
        inner_height = float(inner.sizing.height or 0.0)
        if host_width > 0.0 and inner_width > 0.0 and inner_width < host_width - 0.5:
            return False
        if host_height > 0.0 and inner_height > 0.0 and inner_height < host_height - 0.5:
            return False
    from figma_flutter_agent.generator.layout.widgets.button.core import (
        _button_ink_surface_params,
    )
    from figma_flutter_agent.parser.interaction.forms import interaction_surface_node

    painted = interaction_surface_node(node)
    if painted is None:
        return False
    fill, border, shadows, gradient, _inner = _button_ink_surface_params(painted)
    return bool(fill or border or shadows or gradient)


def prepare_layout_children(
    node: CleanDesignTreeNode,
    *,
    is_layout_root: bool,
    parent_node: CleanDesignTreeNode | None,
) -> tuple[list[CleanDesignTreeNode], bool, set[str], set[str], set[str], set[str], list[str]]:
    """Return sorted children, metadata host flag, omit sets, and merged thumb widgets."""
    sorted_children = _sort_absolute_stack_children(
        node.children,
        is_layout_root=is_layout_root,
    )
    from figma_flutter_agent.generator.layout.widgets.hero import (
        layout_fact_hero_editorial_cover_stack,
        sort_hero_editorial_cover_stack_children,
    )

    if layout_fact_hero_editorial_cover_stack(node):
        sorted_children = sort_hero_editorial_cover_stack_children(node, sorted_children)
    metadata_column_host = (
        not is_layout_root
        and node.type == NodeType.STACK
        and stack_should_emit_as_metadata_column(node, parent_node=parent_node)
    )
    if metadata_column_host:
        sorted_children = sorted(
            sorted_children,
            key=lambda child: (stack_child_ordinal_top(child), child.id),
        )
    paired_circle_ids: set[str] = set()
    merged_thumb_widgets: list[str] = []
    omit_child_ids: set[str] = set()
    playback_seek_ids: set[str] = set()
    playback_decor_omit_ids: set[str] = set()
    if node.type == NodeType.STACK:
        playback_seek_ids = _playback_seek_vector_ids(node)
        if playback_seek_ids:
            playback_decor_omit_ids = _playback_seek_omit_child_ids(node)
    if node.type == NodeType.STACK:
        circle_pair = (
            _find_concentric_circle_pair(sorted_children) if not playback_seek_ids else None
        )
        if circle_pair is not None:
            outer, inner = circle_pair
            paired_circle_ids = {outer.id, inner.id}
            merged_thumb_widgets = _render_concentric_circle_thumb(
                outer,
                inner,
                stack_siblings=sorted_children,
            )
        if not is_layout_root and stack_interaction_kind(node) == "button":
            from figma_flutter_agent.generator.layout.flex_policy.stack import (
                layout_fact_icon_badge_stack,
            )

            surface = primary_surface_node(node)
            if surface is not None and surface_covers_node(node, surface):
                if not layout_fact_icon_badge_stack(node) and _button_covering_surface_may_omit(
                    node,
                    surface,
                    sorted_children,
                ):
                    omit_child_ids.add(surface.id)
    if node.type == NodeType.BUTTON:
        from figma_flutter_agent.parser.interaction.buttons import button_painted_overlay_surface
        from figma_flutter_agent.parser.interaction.icons import (
            layout_fact_button_has_occluding_icon_fill_plate,
            layout_fact_occluding_icon_fill_plate,
        )

        for stack_child in sorted_children:
            if layout_fact_occluding_icon_fill_plate(stack_child, parent=node):
                omit_child_ids.add(stack_child.id)
        if not layout_fact_button_has_occluding_icon_fill_plate(node):
            surface = button_painted_overlay_surface(node) or primary_surface_node(node)
            if surface is not None and surface_covers_node(node, surface):
                omit_child_ids.add(surface.id)
    if node.type == NodeType.STACK:
        from figma_flutter_agent.parser.interaction import (
            layout_fact_stack_hero_full_bleed_scrim,
            layout_fact_stack_product_recommendation_hero,
        )
        from figma_flutter_agent.parser.interaction.icons import (
            layout_fact_compact_icon_glyph_host,
            layout_fact_icon_glyph_frame_placeholder,
        )

        if layout_fact_stack_product_recommendation_hero(node):
            for stack_child in sorted_children:
                if layout_fact_stack_hero_full_bleed_scrim(stack_child):
                    omit_child_ids.add(stack_child.id)
        if layout_fact_compact_icon_glyph_host(node):
            from figma_flutter_agent.generator.layout.flex_policy.stack import (
                layout_fact_icon_badge_stack,
            )
            from figma_flutter_agent.parser.interaction.icons import (
                layout_fact_occluding_icon_fill_plate,
            )

            for stack_child in sorted_children:
                if layout_fact_occluding_icon_fill_plate(stack_child, parent=node):
                    omit_child_ids.add(stack_child.id)
                elif layout_fact_icon_glyph_frame_placeholder(stack_child, parent=node):
                    if not layout_fact_icon_badge_stack(node):
                        omit_child_ids.add(stack_child.id)
    return (
        sorted_children,
        metadata_column_host,
        paired_circle_ids,
        omit_child_ids,
        playback_seek_ids,
        playback_decor_omit_ids,
        merged_thumb_widgets,
    )


def build_flow_context(
    node: CleanDesignTreeNode,
    *,
    child_widgets: list[str],
    sorted_children: list[CleanDesignTreeNode],
    emitted_pairs: list[tuple[CleanDesignTreeNode, str]],
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None,
    is_layout_root: bool,
    scroll_content_root: bool,
    metadata_column_host: bool,
    paired_circle_ids: set[str],
    omit_child_ids: set[str],
    playback_seek_ids: set[str],
    playback_decor_omit_ids: set[str],
    playback_seek_widget: str | None,
) -> dict[str, Any]:
    """Assemble the flow dict consumed by per-type layout renderers."""
    main_axis = resolve_main_axis_alignment(
        node,
        scroll_content_root=scroll_content_root,
        parent_type=parent_type,
        parent_node=parent_node,
    )
    cross_axis = resolve_cross_axis_alignment(
        node,
        parent_type=parent_type,
        cross=node.alignment.cross,
        parent_node=parent_node,
    )
    return {
        "parent_type": parent_type,
        "parent_node": parent_node,
        "is_layout_root": is_layout_root,
        "scroll_content_root": scroll_content_root,
        "child_widgets": child_widgets,
        "sorted_children": sorted_children,
        "emitted_pairs": emitted_pairs,
        "metadata_column_host": metadata_column_host,
        "main_axis": main_axis,
        "cross_axis": cross_axis,
        "paired_circle_ids": paired_circle_ids,
        "omit_child_ids": omit_child_ids,
        "playback_seek_ids": playback_seek_ids,
        "playback_decor_omit_ids": playback_decor_omit_ids,
        "playback_seek_widget": playback_seek_widget,
    }


def render_layout_shell(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    ctx: dict[str, Any],
    flow: dict[str, Any],
    recurse: RecurseFn | None = None,
) -> str:
    """Emit a layout node using pre-built child widget expressions."""
    if node.type == NodeType.TEXT:
        if recurse is None:
            msg = "render_layout_shell TEXT requires recurse"
            raise ValueError(msg)
        return render_text_node(node, ctx, flow, recurse=recurse)

    if node.type in {NodeType.IMAGE, NodeType.VECTOR}:
        result = render_image_or_vector(node, ctx, flow)
        if result is not None:
            return result

    if node.image_asset_key and not node.children:
        result = render_misc.image_asset_leaf(node, ctx, flow)
        if result is not None:
            return result

    result = render_simple_controls(node, ctx, flow)
    if result is not None:
        return result

    if node.type == NodeType.BUTTON:
        if recurse is None:
            msg = "render_layout_shell BUTTON requires recurse"
            raise ValueError(msg)
        return render_button_node(node, ctx, flow, recurse=recurse)

    if node.type == NodeType.INPUT:
        return render_input_node(node, ctx, flow)

    if node.type == NodeType.CARD:
        return render_card(node, ctx, flow)

    result = render_tabs_carousel_bottomnav_wrap(node, ctx, flow)
    if result is not None:
        return result

    if node.type == NodeType.GRID:
        return render_grid(node, ctx, flow)

    if node.type == NodeType.ROW:
        if recurse is None:
            msg = "render_layout_shell ROW requires recurse"
            raise ValueError(msg)
        return render_row(node, ctx, flow, recurse=recurse)

    if node.type == NodeType.COLUMN:
        return render_column(node, ctx, flow)

    if node.type == NodeType.STACK:
        if recurse is None:
            msg = "render_layout_shell STACK requires recurse"
            raise ValueError(msg)
        return render_stack(node, ctx, flow, recurse=recurse)

    return render_misc.fallback(node, ctx, flow)


def assemble_layout_emit(
    node: CleanDesignTreeNode,
    *,
    ctx: dict[str, Any],
    recurse: RecurseFn,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None,
    is_layout_root: bool,
    scroll_content_root: bool,
    uses_svg: bool,
    theme_variant: str,
    cluster_classes: dict[str, str] | None,
    cluster_vector_variants: dict | None,
    cluster_vector_variant: object,
    skip_cluster_id: str | None,
    responsive_enabled: bool,
    design_artboard_width: float | None,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Build child widgets via recurse and emit the layout shell for ``node``."""
    (
        sorted_children,
        metadata_column_host,
        paired_circle_ids,
        omit_child_ids,
        playback_seek_ids,
        playback_decor_omit_ids,
        merged_thumb_widgets,
    ) = prepare_layout_children(
        node,
        is_layout_root=is_layout_root,
        parent_node=parent_node,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_should_suppress_inner_positioned_for_pin_bottom_scroll,
    )
    from figma_flutter_agent.generator.layout.widgets.positioned import (
        _stack_has_bottom_anchored_child,
    )

    from .containers import card_should_emit_as_overlay_stack

    pin_bottom_chrome = node.type == NodeType.STACK and _stack_has_bottom_anchored_child(node)

    from ..input.absolute_fields import build_decomposed_absolute_field_widgets

    field_widgets_by_shell_id, field_omit_ids = build_decomposed_absolute_field_widgets(
        sorted_children,
        theme_variant=theme_variant,
        parent_type=node.type,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    omit_child_ids |= field_omit_ids

    child_parent_type = (
        NodeType.STACK
        if card_should_emit_as_overlay_stack(node)
        else NodeType.COLUMN
        if metadata_column_host
        else node.type
    )
    child_widgets: list[str] = []
    emitted_pairs: list[tuple[CleanDesignTreeNode, str]] = []
    for child in sorted_children:
        if child.id in field_widgets_by_shell_id:
            widget = field_widgets_by_shell_id[child.id]
            child_widgets.append(widget)
            emitted_pairs.append((child, widget))
            continue
        if (
            child.id in paired_circle_ids
            or child.id in omit_child_ids
            or child.id in playback_seek_ids
            or child.id in playback_decor_omit_ids
        ):
            continue
        child_scroll_root = scroll_content_root or (
            pin_bottom_chrome
            and stack_child_should_suppress_inner_positioned_for_pin_bottom_scroll(child)
        )
        widget = recurse(
            child,
            uses_svg=uses_svg,
            parent_type=child_parent_type,
            parent_node=node,
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
            scroll_content_root=child_scroll_root,
        )
        child_widgets.append(widget)
        emitted_pairs.append((child, widget))
    if merged_thumb_widgets:
        child_widgets.extend(merged_thumb_widgets)
    playback_seek_widget: str | None = None
    if playback_seek_ids:
        playback_seek_widget = _render_playback_seek_slider(node)
    flow = build_flow_context(
        node,
        child_widgets=child_widgets,
        sorted_children=sorted_children,
        emitted_pairs=emitted_pairs,
        parent_type=parent_type,
        parent_node=parent_node,
        is_layout_root=is_layout_root,
        scroll_content_root=scroll_content_root,
        metadata_column_host=metadata_column_host,
        paired_circle_ids=paired_circle_ids,
        omit_child_ids=omit_child_ids,
        playback_seek_ids=playback_seek_ids,
        playback_decor_omit_ids=playback_decor_omit_ids,
        playback_seek_widget=playback_seek_widget,
    )
    return render_layout_shell(node, child_widgets, ctx=ctx, flow=flow, recurse=recurse)


def render_leaf_body(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    parent_type: NodeType | None = None,
    parent_node: CleanDesignTreeNode | None = None,
    theme_variant: str = "material_3",
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
    cluster_vector_variant: object = None,
    skip_cluster_id: str | None = None,
    responsive_enabled: bool = False,
    is_layout_root: bool = False,
    design_artboard_width: float | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    de_archetype_pass: bool = False,
    scroll_content_root: bool = False,
) -> str:
    """Render a node with the full geometric dispatcher (including child recursion)."""
    from .dispatch import render_node_body

    return render_node_body(
        node,
        uses_svg=uses_svg,
        parent_type=parent_type,
        parent_node=parent_node,
        theme_variant=theme_variant,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        cluster_vector_variant=cluster_vector_variant,
        skip_cluster_id=skip_cluster_id,
        responsive_enabled=responsive_enabled,
        is_layout_root=is_layout_root,
        design_artboard_width=design_artboard_width,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        de_archetype_pass=de_archetype_pass,
        scroll_content_root=scroll_content_root,
    )
