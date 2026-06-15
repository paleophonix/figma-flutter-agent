"""Sync ambient layer with foreground scaling and centered design canvas.

Re-exports from ``sync_blocks``, ``sync_hoist``, and ``sync_canvas`` for
backward compatibility.
"""

from __future__ import annotations

from .sync_blocks import (
    _extract_asset_paths,
    _find_matching_bracket,
    _iter_direct_stack_children_blocks,
    _iter_positioned_blocks,
)
from .sync_canvas import ensure_centered_design_canvas
from .sync_hoist import (
    _ambient_stack_inner,
    _canvas_size_tokens,
    _hoist_ambient_background_behind_canvas,
    _inject_ambient_into_expand_stack,
    _rebuild_ambient_positioned_fill,
    _remove_ambient_positioned_blocks,
    _wrap_positioned_fill_with_cover,
    fix_ambient_background_responsiveness,
    sync_ambient_layer_with_foreground_scaling,
)

__all__ = [
    "_ambient_stack_inner",
    "_canvas_size_tokens",
    "_extract_asset_paths",
    "_find_matching_bracket",
    "_hoist_ambient_background_behind_canvas",
    "_inject_ambient_into_expand_stack",
    "_iter_direct_stack_children_blocks",
    "_iter_positioned_blocks",
    "_rebuild_ambient_positioned_fill",
    "_remove_ambient_positioned_blocks",
    "_wrap_positioned_fill_with_cover",
    "ensure_centered_design_canvas",
    "fix_ambient_background_responsiveness",
    "sync_ambient_layer_with_foreground_scaling",
]
