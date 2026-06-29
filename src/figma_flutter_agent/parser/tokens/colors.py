"""Color token extraction helpers."""

from __future__ import annotations

from collections import Counter

from figma_flutter_agent.parser.tokens.naming import allocate_token_name

_NEUTRAL_THRESHOLD = 0.05


def rgba_to_argb_hex(color: dict[str, float]) -> str:
    """Convert Figma RGBA (0-1 floats) to Flutter ARGB hex string."""
    alpha = int(round((color.get("a", 1.0)) * 255))
    red = int(round(color.get("r", 0) * 255))
    green = int(round(color.get("g", 0) * 255))
    blue = int(round(color.get("b", 0) * 255))
    return f"0x{alpha:02X}{red:02X}{green:02X}{blue:02X}"


def solid_paint_to_argb_hex(
    color: dict[str, float],
    *,
    paint_opacity: float = 1.0,
) -> str:
    """Compose Figma SOLID paint color and paint-level opacity into one ARGB hex."""
    combined_alpha = float(color.get("a", 1.0)) * float(paint_opacity)
    return rgba_to_argb_hex(
        {
            "r": color.get("r", 0.0),
            "g": color.get("g", 0.0),
            "b": color.get("b", 0.0),
            "a": combined_alpha,
        }
    )


def is_neutral_rgba(color: dict[str, float]) -> bool:
    """Return True when a color is near white or near black."""
    red = color.get("r", 0.0)
    green = color.get("g", 0.0)
    blue = color.get("b", 0.0)
    if (
        red > 1 - _NEUTRAL_THRESHOLD
        and green > 1 - _NEUTRAL_THRESHOLD
        and blue > 1 - _NEUTRAL_THRESHOLD
    ):
        return True
    return red < _NEUTRAL_THRESHOLD and green < _NEUTRAL_THRESHOLD and blue < _NEUTRAL_THRESHOLD


def _argb_luminance(hex_value: str) -> float:
    """Return relative luminance (0-1) from an ``0xAARRGGBB`` string."""
    digits = hex_value.removeprefix("0x")
    if len(digits) != 8:
        return 0.0
    red = int(digits[2:4], 16) / 255.0
    green = int(digits[4:6], 16) / 255.0
    blue = int(digits[6:8], 16) / 255.0
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def select_primary_color_hex(color_counts: Counter[str], neutral_hexes: set[str]) -> str | None:
    """Pick the most frequent non-neutral fill color for the primary token."""
    for hex_value, _count in color_counts.most_common():
        if hex_value not in neutral_hexes:
            return hex_value
    return None


def select_neutral_primary_hex(color_counts: Counter[str], neutral_hexes: set[str]) -> str | None:
    """Pick primary from neutral palette: most frequent, then darkest for contrast."""
    candidates = [
        (hex_value, count)
        for hex_value, count in color_counts.most_common()
        if hex_value in neutral_hexes
    ]
    if not candidates:
        return None
    max_count = max(count for _, count in candidates)
    tied = [hex_value for hex_value, count in candidates if count == max_count]
    return min(tied, key=_argb_luminance)


def build_color_tokens(color_counts: Counter[str], neutral_hexes: set[str]) -> dict[str, str]:
    """Build flat color tokens with a frequency-based primary seed color."""
    primary_hex = select_primary_color_hex(color_counts, neutral_hexes)
    if primary_hex is None:
        primary_hex = select_neutral_primary_hex(color_counts, neutral_hexes)
    if primary_hex is None:
        return {}

    used_names = {"primary"}
    colors: dict[str, str] = {"primary": primary_hex}
    seen_hex = {primary_hex}

    for hex_value, _count in color_counts.most_common():
        if hex_value in seen_hex:
            continue
        token_name = allocate_token_name(f"color{len(colors)}", used_names)
        colors[token_name] = hex_value
        seen_hex.add(hex_value)

    return colors
