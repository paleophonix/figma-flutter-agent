"""Public API of the render package — re-exports for backward-compatible imports."""

from .decoration import _decorate_widget_with_box_decoration
from .emit import render_node_body
from .flex_sizing import (
    _wrap_center_preserving_flex_parent_data,
    _wrap_sizing,
)
from .input import _input_content_padding
from .playback import _sizing_like_skip_control
from .position import (
    _child_needs_positioned_bounds,
    _ensure_positioned_stack_bounds,
    _wrap_root_column_viewport,
    _wrap_root_stack_viewport,
)
from .positioned import (
    _apply_layout_slot_wraps,
    _positioned_fields,
    _stack_has_bottom_anchored_child,
)
from .shared import (
    _node_layout_size,
    figma_positioned_dimensions,
    snap_device_pixels_scope,
)
from .svg import (
    SVG_PATH_RASTER_THRESHOLD,
    _apply_node_transform,
    _is_skip_control_stack,
    _render_exported_vector,
    _vector_needs_baked_raster,
)
from .text import (
    _apply_stack_position,
    _render_explicit_multiline_text_lines,
)

__all__ = [
    "render_node_body",
    "figma_positioned_dimensions",
    "snap_device_pixels_scope",
    "_node_layout_size",
    "_apply_layout_slot_wraps",
    "_apply_node_transform",
    "_apply_stack_position",
    "_child_needs_positioned_bounds",
    "_decorate_widget_with_box_decoration",
    "_ensure_positioned_stack_bounds",
    "_input_content_padding",
    "_is_skip_control_stack",
    "_positioned_fields",
    "_render_explicit_multiline_text_lines",
    "_render_exported_vector",
    "_sizing_like_skip_control",
    "_stack_has_bottom_anchored_child",
    "_vector_needs_baked_raster",
    "_wrap_center_preserving_flex_parent_data",
    "_wrap_root_column_viewport",
    "_wrap_root_stack_viewport",
    "_wrap_sizing",
    "SVG_PATH_RASTER_THRESHOLD",
]
