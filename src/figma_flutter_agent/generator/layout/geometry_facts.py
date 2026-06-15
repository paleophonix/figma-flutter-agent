"""Universal geometry band facts for flex-policy classification (T3).

Named thresholds and pure sizing/padding predicates — no screen names or figma ids.
"""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, Padding, Sizing

# Row / chip bands (logical px).
STATUS_PILL_MAX_HEIGHT = 36.0
TIGHT_PILL_MAX_HEIGHT = 30.0
SQUARE_ICON_CONTROL_MIN = 40.0
SQUARE_ICON_CONTROL_MAX = 56.0
COMPACT_CHIP_HOST_MAX_WIDTH = 140.0
MIN_CHIP_HORIZONTAL_PADDING = 8.0

# Column bands.
TIGHT_STACK_TEXT_MAX_HEIGHT = 28.0
SQUARE_TILE_MIN_EDGE = 64.0
SQUARE_TILE_ASPECT_TOLERANCE = 8.0
SQUARE_TILE_ASPECT_RATIO = 0.12
PRODUCT_TILE_WIDTH_MIN = 120.0
PRODUCT_TILE_WIDTH_MAX = 200.0
CARD_METADATA_MAX_WIDTH = 120.0
NUMERIC_GLYPH_OVERLAY_MAX_WIDTH = 24.0
CENTER_HUG_WIDTH_EPSILON = 1.0

# Stack bands.
STACK_PANEL_MIN_HEIGHT = 60.0
CARD_METADATA_STACK_MAX_WIDTH = 120.0
CARD_METADATA_STACK_MIN_HEIGHT = 40.0
CARD_METADATA_STACK_MAX_HEIGHT = 64.0
CIRCULAR_OPTION_MIN_EXTENT = 32.0
CIRCULAR_OPTION_MAX_EXTENT = 56.0
CARD_HERO_MIN_WIDTH = 120.0
CARD_HERO_MIN_HEIGHT = 80.0
CARD_HERO_MIN_HEIGHT_RATIO = 0.45
SUBTITLE_STACK_STRUT_BUFFER = 2.0
SUBTITLE_LINE_MAX_HEIGHT = 24.0
VIEWPORT_CHROME_MIN_WIDTH = 360.0
VIEWPORT_CHROME_MAX_WIDTH = 430.0
VIEWPORT_CHROME_MAX_HEIGHT = 50.0
SMALL_VECTOR_MAX_EXTENT = 18.0


def positive_finite(value: float | None) -> float | None:
    """Return ``value`` when it is a positive finite number."""
    if value is None:
        return None
    numeric = float(value)
    if numeric <= 0:
        return None
    return numeric


def height_within_band(
    height: float | None,
    *,
    max_height: float,
    min_height: float = 0.0,
) -> bool:
    """Return True when ``height`` lies in ``(min_height, max_height]``."""
    resolved = positive_finite(height)
    if resolved is None:
        return False
    return min_height < resolved <= max_height


def width_within_band(
    width: float | None,
    *,
    min_width: float,
    max_width: float,
) -> bool:
    """Return True when ``width`` lies in ``[min_width, max_width]``."""
    resolved = positive_finite(width)
    if resolved is None:
        return False
    return min_width <= resolved <= max_width


def square_bounds_within_band(
    width: float | None,
    height: float | None,
    *,
    min_edge: float,
    max_edge: float,
) -> bool:
    """Return True when width and height are both inside ``[min_edge, max_edge]``."""
    resolved_width = positive_finite(width)
    resolved_height = positive_finite(height)
    if resolved_width is None or resolved_height is None:
        return False
    return min_edge <= resolved_width <= max_edge and min_edge <= resolved_height <= max_edge


def square_tile_min_extent(width: float | None, height: float | None, *, min_edge: float) -> bool:
    """Return True when both dimensions meet ``min_edge``."""
    resolved_width = positive_finite(width)
    resolved_height = positive_finite(height)
    if resolved_width is None or resolved_height is None:
        return False
    return resolved_width >= min_edge and resolved_height >= min_edge


def near_square_aspect(
    width: float,
    height: float,
    *,
    tolerance: float = SQUARE_TILE_ASPECT_TOLERANCE,
    ratio_cap: float = SQUARE_TILE_ASPECT_RATIO,
) -> bool:
    """Return True when width and height are within a square aspect tolerance."""
    return abs(width - height) <= max(tolerance, width * ratio_cap)


def horizontal_padding_sum(padding: Padding | None) -> float:
    """Return combined left+right padding in logical pixels."""
    if padding is None:
        return 0.0
    return float(padding.left or 0.0) + float(padding.right or 0.0)


def node_horizontal_padding_at_least(node: CleanDesignTreeNode, minimum: float) -> bool:
    """Return True when node horizontal padding meets ``minimum``."""
    return horizontal_padding_sum(node.padding) >= minimum


def bounded_width_at_most(sizing: Sizing, maximum: float) -> bool:
    """Return True when node width is positive and not wider than ``maximum``."""
    width = positive_finite(sizing.width)
    if width is None:
        return False
    return width <= maximum


def viewport_chrome_band_size(width: float | None, height: float | None) -> bool:
    """Return True when dimensions match a full-bleed status/home chrome band."""
    resolved_width = positive_finite(width)
    resolved_height = positive_finite(height)
    if resolved_width is None or resolved_height is None:
        return False
    return (
        VIEWPORT_CHROME_MIN_WIDTH <= resolved_width <= VIEWPORT_CHROME_MAX_WIDTH
        and resolved_height <= VIEWPORT_CHROME_MAX_HEIGHT
    )
