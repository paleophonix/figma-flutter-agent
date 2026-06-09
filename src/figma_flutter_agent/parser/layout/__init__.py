"""parser/layout — Auto Layout to semantic layout mapping helpers."""

from .grid import (
    extract_grid_column_count,
    extract_grid_gaps,
    extract_scroll_axis,
    infer_container_type,
)
from .placement import (
    _infer_stack_child_top,
    _sync_sizing_width_to_placement,
    clamp_stack_child_placement_to_parent,
    extract_layout_position,
    extract_stack_placement,
    reconcile_stack_placement_top_from_edges,
    reconcile_stack_placements_in_tree,
    refine_text_stack_placement,
)
from .reconcilers import (
    _is_auth_pill_container,
    _is_brand_wordmark_stack,
    _is_promo_card_stack,
    _is_top_centered_brand_mark,
    _stack_has_playback_timestamps,
    promote_flex_hosts_with_absolute_children,
    reconcile_auth_button_icon_placements_in_tree,
    reconcile_centered_text_placements_in_tree,
    reconcile_consent_checkbox_rows_in_tree,
    reconcile_cta_footer_surfaces_in_tree,
    reconcile_logo_wordmark_top_in_tree,
    reconcile_playback_timestamp_row_in_tree,
    reconcile_promo_card_row_tops_in_tree,
    reconcile_title_subtitle_stacks_in_tree,
    reconcile_weekday_chip_row_in_tree,
)
from .sizing import (
    _constraint_axis,
    _visible_figma_children,
    adjust_sizing_for_visible_children,
    enforce_fixed_sizing_for_stack_and_button,
    extract_alignment,
    extract_padding,
    extract_sizing,
    map_alignment,
    map_sizing_mode,
)

__all__ = [
    # sizing
    "map_alignment",
    "map_sizing_mode",
    "extract_padding",
    "enforce_fixed_sizing_for_stack_and_button",
    "_visible_figma_children",
    "adjust_sizing_for_visible_children",
    "extract_sizing",
    "extract_alignment",
    "_constraint_axis",
    # placement
    "extract_stack_placement",
    "reconcile_stack_placement_top_from_edges",
    "clamp_stack_child_placement_to_parent",
    "_sync_sizing_width_to_placement",
    "reconcile_stack_placements_in_tree",
    "extract_layout_position",
    "refine_text_stack_placement",
    "_infer_stack_child_top",
    # reconcilers
    "_is_promo_card_stack",
    "reconcile_promo_card_row_tops_in_tree",
    "_is_auth_pill_container",
    "reconcile_auth_button_icon_placements_in_tree",
    "promote_flex_hosts_with_absolute_children",
    "reconcile_consent_checkbox_rows_in_tree",
    "reconcile_weekday_chip_row_in_tree",
    "reconcile_title_subtitle_stacks_in_tree",
    "_is_top_centered_brand_mark",
    "_is_brand_wordmark_stack",
    "reconcile_cta_footer_surfaces_in_tree",
    "_stack_has_playback_timestamps",
    "reconcile_playback_timestamp_row_in_tree",
    "reconcile_logo_wordmark_top_in_tree",
    "reconcile_centered_text_placements_in_tree",
    # grid
    "extract_scroll_axis",
    "extract_grid_column_count",
    "extract_grid_gaps",
    "infer_container_type",
]
