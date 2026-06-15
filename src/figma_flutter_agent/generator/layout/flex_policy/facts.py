"""Geometry-driven layout fact helpers (Wave F / flex_policy facade).

Public emit and flex-policy code should import layout facts from this module
when crossing package boundaries; sibling modules may define facts locally.
"""

from figma_flutter_agent.generator.layout.flex_policy.column import (
    layout_fact_column_card_metadata_slot,
    layout_fact_column_oversized_photo_clip_host,
    layout_fact_column_product_card_footer_margin,
    layout_fact_column_product_tile_metadata,
    layout_fact_column_tight_stack_text_host,
)
from figma_flutter_agent.generator.layout.flex_policy.row import (
    layout_fact_row_card_composite_body,
    layout_fact_row_icon_stepper_control_row,
    layout_fact_row_label_value_summary_row,
    layout_fact_row_numeric_counter_badge,
    layout_fact_row_product_card_price_footer_row,
    layout_fact_row_space_between_text_metric_row,
    layout_fact_row_status_pill_badge,
    layout_fact_row_tight_horizontal_chip,
    layout_fact_row_tight_horizontal_pill_label,
    layout_fact_row_tight_overflow_guard_label_row,
    layout_fact_row_toolbar_leading_title_row,
)
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    layout_fact_stack_card_metadata_host,
    layout_fact_stack_circular_option_glyph_host,
    layout_fact_stack_numeric_glyph_overlay_host,
    layout_fact_stack_positioned_subtitle_line,
)

__all__ = [
    "layout_fact_column_card_metadata_slot",
    "layout_fact_column_oversized_photo_clip_host",
    "layout_fact_column_product_card_footer_margin",
    "layout_fact_column_product_tile_metadata",
    "layout_fact_column_tight_stack_text_host",
    "layout_fact_row_card_composite_body",
    "layout_fact_row_icon_stepper_control_row",
    "layout_fact_row_label_value_summary_row",
    "layout_fact_row_numeric_counter_badge",
    "layout_fact_row_product_card_price_footer_row",
    "layout_fact_row_space_between_text_metric_row",
    "layout_fact_row_status_pill_badge",
    "layout_fact_row_tight_horizontal_chip",
    "layout_fact_row_tight_horizontal_pill_label",
    "layout_fact_row_tight_overflow_guard_label_row",
    "layout_fact_row_toolbar_leading_title_row",
    "layout_fact_stack_card_metadata_host",
    "layout_fact_stack_circular_option_glyph_host",
    "layout_fact_stack_numeric_glyph_overlay_host",
    "layout_fact_stack_positioned_subtitle_line",
]
