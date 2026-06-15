"""Ambient background generation package."""

from .detection import (
    _collect_all_nodes,
    _has_decorative_vector_name,
    _has_playback_timeline_markers,
    _is_ambient_background_child,
    _is_navigation_chrome_stack,
    _is_playback_chrome_stack,
    _subtree_has_interactive_ui,
    is_screen_wallpaper_node,
)
from .partition import (
    collect_ambient_background_children,
    partition_wallpaper_foreground_tree,
    split_screen_wallpaper_children,
)
from .render import (
    _ambient_canvas_fill_expr,
    _collect_node_asset_keys,
    patch_scaffold_background_from_tree,
    render_ambient_background_layer,
    render_ambient_decorative_node,
    render_screen_wallpaper_layer,
    resolve_screen_canvas_background_expr,
)
from .sync import (
    _ambient_stack_inner,
    _canvas_size_tokens,
    _extract_asset_paths,
    _find_matching_bracket,
    _hoist_ambient_background_behind_canvas,
    _inject_ambient_into_expand_stack,
    _iter_positioned_blocks,
    _rebuild_ambient_positioned_fill,
    _remove_ambient_positioned_blocks,
    _wrap_positioned_fill_with_cover,
    ensure_centered_design_canvas,
    fix_ambient_background_responsiveness,
    sync_ambient_layer_with_foreground_scaling,
)

__all__ = [
    "collect_ambient_background_children",
    "fix_ambient_background_responsiveness",
    "is_screen_wallpaper_node",
    "partition_wallpaper_foreground_tree",
    "patch_scaffold_background_from_tree",
    "render_ambient_background_layer",
    "render_ambient_decorative_node",
    "render_screen_wallpaper_layer",
    "resolve_screen_canvas_background_expr",
    "split_screen_wallpaper_children",
    "ensure_centered_design_canvas",
    "sync_ambient_layer_with_foreground_scaling",
]
