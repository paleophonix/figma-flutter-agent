"""Vertical diff-band metrics."""

from __future__ import annotations

from PIL import Image, ImageChops

from figma_flutter_agent.validation.pixel.models import DiffBandRegion


def _count_changed_pixels_in_band(
    diff: Image.Image,
    *,
    y_start: int,
    y_end: int,
    channel_tolerance: int,
) -> int:
    pixels = diff.load()
    assert pixels is not None
    width, _height = diff.size
    changed = 0
    for y in range(y_start, y_end):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if max(red, green, blue, alpha) > channel_tolerance:
                changed += 1
    return changed


def compute_vertical_diff_bands(
    reference: Image.Image,
    actual: Image.Image,
    *,
    channel_tolerance: int = 16,
    band_count: int = 3,
) -> tuple[DiffBandRegion, ...]:
    """Split the diff into vertical bands and compute changed-pixel ratios."""
    diff = ImageChops.difference(reference, actual)
    _width, height = diff.size
    if height <= 0 or band_count <= 0:
        return ()

    band_height = max(height // band_count, 1)
    names = (
        ("top", "middle", "bottom")
        if band_count == 3
        else tuple(f"band_{index + 1}" for index in range(band_count))
    )
    regions: list[DiffBandRegion] = []
    for index in range(band_count):
        y_start = index * band_height
        y_end = height if index == band_count - 1 else min((index + 1) * band_height, height)
        band_pixels = max((y_end - y_start) * diff.size[0], 1)
        changed = _count_changed_pixels_in_band(
            diff,
            y_start=y_start,
            y_end=y_end,
            channel_tolerance=channel_tolerance,
        )
        name = names[index] if index < len(names) else f"band_{index + 1}"
        regions.append(
            DiffBandRegion(
                name=name,
                changed_ratio=changed / band_pixels,
                y_start=y_start,
                y_end=y_end,
            )
        )
    return tuple(regions)
