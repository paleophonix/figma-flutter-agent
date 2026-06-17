"""Resolve Flutter golden/capture and Chrome preview viewport sizes."""

from __future__ import annotations

from figma_flutter_agent.config.models import ResponsiveConfig
from figma_flutter_agent.dev.preview_size import chrome_preview_dart_defines


def resolve_capture_surface_size(
    *,
    artboard_width: int,
    artboard_height: int,
) -> tuple[int, int]:
    """Return artboard ``(width, height)`` for golden/capture ``setSurfaceSize``.

    Capture is always 1:1 with the Figma frame regardless of ``adaptive_render``.

    Args:
        artboard_width: Parsed Figma frame width in logical pixels.
        artboard_height: Parsed Figma frame height in logical pixels.

    Returns:
        Positive integer surface dimensions.
    """
    return max(int(artboard_width), 1), max(int(artboard_height), 1)


def capture_render_dart_defines(*, surface_width: int, surface_height: int) -> list[str]:
    """Return artboard preview ``--dart-define`` flags for ``flutter test`` capture."""
    return chrome_preview_dart_defines(
        surface_width,
        surface_height,
        capture_mode=True,
    )


def resolve_chrome_preview_size(
    *,
    artboard_width: int,
    artboard_height: int,
    responsive: ResponsiveConfig,
) -> tuple[int, int]:
    """Return Chrome window size from artboard and responsive settings.

    When ``adaptive_render`` is enabled, width expands to ``max_web_width`` so
    ``LayoutBuilder`` breakpoints are exercised. Otherwise the Figma artboard
    size is used.

    Args:
        artboard_width: Parsed Figma frame width in logical pixels.
        artboard_height: Parsed Figma frame height in logical pixels.
        responsive: Agent responsive settings.

    Returns:
        Positive integer window dimensions.
    """
    safe_w = max(int(artboard_width), 1)
    safe_h = max(int(artboard_height), 1)
    if responsive.adaptive_render:
        return max(int(responsive.max_web_width), safe_w), safe_h
    return safe_w, safe_h


def chrome_preview_dart_defines_for_responsive(
    *,
    surface_width: int,
    surface_height: int,
    responsive: ResponsiveConfig,
) -> list[str]:
    """Return artboard dart-defines for Chrome when not in adaptive mode."""
    if responsive.adaptive_render:
        return []
    return chrome_preview_dart_defines(surface_width, surface_height)
