"""Shared constants, context vars, and micro-utilities used across render submodules."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from figma_flutter_agent.schemas import CleanDesignTreeNode, StackPlacement

_MAIN_AXIS = {
    "start": "MainAxisAlignment.start",
    "end": "MainAxisAlignment.end",
    "center": "MainAxisAlignment.center",
    "spaceBetween": "MainAxisAlignment.spaceBetween",
    "stretch": "MainAxisAlignment.spaceBetween",
    "baseline": "MainAxisAlignment.start",
}

_CROSS_AXIS = {
    "start": "CrossAxisAlignment.start",
    "end": "CrossAxisAlignment.end",
    "center": "CrossAxisAlignment.center",
    "spaceBetween": "CrossAxisAlignment.center",
    "stretch": "CrossAxisAlignment.stretch",
    "baseline": "CrossAxisAlignment.baseline",
}

_ICON_BUTTON_MAX_SIZE = 80.0
_OVERLAY_TEXT_MAX_SIZE = 60.0

_snap_device_pixels_ctx: ContextVar[bool] = ContextVar(
    "snap_device_pixels", default=False
)


@contextmanager
def snap_device_pixels_scope(enabled: bool):
    """Enable logical-to-physical pixel snapping for positioned layout emit (FID-45)."""
    token = _snap_device_pixels_ctx.set(enabled)
    try:
        yield
    finally:
        _snap_device_pixels_ctx.reset(token)


def _node_layout_size(
    node: CleanDesignTreeNode,
    placement: StackPlacement | None,
) -> tuple[float | None, float | None]:
    """Resolve Figma frame size for bounded Stack / Positioned codegen."""
    width = node.sizing.width
    height = node.sizing.height
    if placement is not None:
        if placement.width is not None and placement.width > 0:
            width = placement.width
        if placement.height is not None and placement.height > 0:
            height = placement.height
    return width, height


def figma_positioned_dimensions(
    node: CleanDesignTreeNode,
    placement: StackPlacement | None = None,
) -> tuple[float | None, float | None]:
    """Return layout width/height for a ``Positioned`` child (never paint-expand)."""
    placement = placement or node.stack_placement
    if placement is None:
        return None, None
    width, height = _node_layout_size(node, placement)
    return (
        width if width is not None and width > 0 else None,
        height if height is not None and height > 0 else None,
    )
