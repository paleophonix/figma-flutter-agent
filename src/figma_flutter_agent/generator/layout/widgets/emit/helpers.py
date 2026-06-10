"""Early-return special-case helpers shared by the top-level dispatcher."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.schemas import CleanDesignTreeNode

from ..button import _try_render_cta_footer_split_stack, _wrap_button_stack
from ..hero import try_render_product_recommendation_hero_stack
from ..thumbnail import try_render_square_product_photo_stack
from ..playback import _try_render_play_pause_stack


def _try_render_early_stack_special_case(
    node: CleanDesignTreeNode,
    ctx: dict,
    *,
    de_archetype_pass: bool,
    parent_node: CleanDesignTreeNode | None,
    recurse,
) -> tuple[str, bool] | None:
    """Render the play-pause / product-photo STACK archetypes ahead of the
    generic dispatch, before cluster-reference and pruning checks run.

    Args:
        node: The STACK node being rendered.
        ctx: Shared rendering context dict (theme, fonts, cluster info).
        de_archetype_pass: Whether archetype shortcuts are disabled.
        parent_node: The parent tree node, used for sizing decisions.
        recurse: The top-level `render_node_body` function for children.

    Returns:
        A tuple of (widget expression, whether parent_node should be used for
        sizing) if one of the archetypes matched, else None.
    """
    theme_variant = ctx["theme_variant"]
    uses_svg = ctx["uses_svg"]
    bundled_font_families = ctx["bundled_font_families"]
    dart_weight_overrides_by_family = ctx["dart_weight_overrides_by_family"]
    text_theme_slot_by_style_name = ctx["text_theme_slot_by_style_name"]
    text_theme_size_slots = ctx["text_theme_size_slots"]

    play_pause_early = (
        None if de_archetype_pass else _try_render_play_pause_stack(node)
    )
    if play_pause_early is not None:
        label = escape_dart_string(node.accessibility_label or node.name)
        play_pause_early = _wrap_button_stack(
            play_pause_early,
            node,
            theme_variant=theme_variant,
        )
        return f"Semantics(label: '{label}', child: {play_pause_early})", False

    photo_stack_early = try_render_product_recommendation_hero_stack(
        node,
        uses_svg=uses_svg,
        render_node_body=recurse,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if photo_stack_early is None:
        photo_stack_early = try_render_square_product_photo_stack(
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
    if photo_stack_early is not None:
        return photo_stack_early, True
    return None


def _try_render_non_root_stack_special_case(
    node: CleanDesignTreeNode,
    ctx: dict,
    *,
    de_archetype_pass: bool,
) -> str | None:
    """Render the weekday-chip-row, wheel-time-picker, and CTA-footer-split
    STACK archetypes for non-layout-root stacks.

    Args:
        node: The non-root STACK node being rendered.
        ctx: Shared rendering context dict (theme, fonts, cluster info).
        de_archetype_pass: Whether archetype shortcuts are disabled.

    Returns:
        A Dart widget expression if one of the archetypes matched, else None.
    """
    from figma_flutter_agent.generator.layout.interactive import (
        render_time_wheel_picker_stack,
        render_weekday_chip_row,
    )
    from figma_flutter_agent.parser.interaction import (
        WEEKDAY_CHIP_ROW_NAME,
        looks_like_wheel_time_picker_stack,
    )

    if node.name == WEEKDAY_CHIP_ROW_NAME:
        return render_weekday_chip_row(node)
    if looks_like_wheel_time_picker_stack(node):
        return render_time_wheel_picker_stack(node)
    if de_archetype_pass:
        return None
    return _try_render_cta_footer_split_stack(
        node,
        uses_svg=ctx["uses_svg"],
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
