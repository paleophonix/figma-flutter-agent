"""Map clean-tree styles to Dart theme expressions for deterministic codegen."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.colors import (
    dart_color_expr,
    fill_luminance,
    gradient_fill_expr,
    is_dark_fill_color,
)
from figma_flutter_agent.generator.layout.style.decoration import (
    border_radius_expr,
    box_decoration_expr,
    box_foreground_decoration_expr,
    card_elevation_expr,
    has_box_decoration,
)
from figma_flutter_agent.generator.layout.style.text import (
    filled_button_label_text_color,
    should_emit_strut_style,
    strut_style_expr,
    text_align_expr,
    text_span_style_expr,
    text_style_expr,
    text_widget_trailing_params,
    wrap_tight_chip_label,
)

__all__ = [
    "border_radius_expr",
    "box_decoration_expr",
    "box_foreground_decoration_expr",
    "card_elevation_expr",
    "dart_color_expr",
    "fill_luminance",
    "filled_button_label_text_color",
    "gradient_fill_expr",
    "has_box_decoration",
    "is_dark_fill_color",
    "should_emit_strut_style",
    "strut_style_expr",
    "text_align_expr",
    "text_span_style_expr",
    "text_style_expr",
    "text_widget_trailing_params",
    "wrap_tight_chip_label",
]
