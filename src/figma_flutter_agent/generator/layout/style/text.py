"""Text, strut, and typography style expressions."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.text_emit import (
    filled_button_label_text_color,
    text_span_style_expr,
    text_style_expr,
)
from figma_flutter_agent.generator.layout.style.text_helpers import (
    should_emit_strut_style,
    strut_style_expr,
    text_align_expr,
    text_widget_trailing_params,
    wrap_gradient_fill_text,
    wrap_painted_pill_scale_down_label,
    wrap_tight_chip_label,
)

__all__ = [
    "filled_button_label_text_color",
    "should_emit_strut_style",
    "strut_style_expr",
    "text_align_expr",
    "text_span_style_expr",
    "text_style_expr",
    "text_widget_trailing_params",
    "wrap_gradient_fill_text",
    "wrap_painted_pill_scale_down_label",
    "wrap_tight_chip_label",
]
