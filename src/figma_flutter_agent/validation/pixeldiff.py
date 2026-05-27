"""Pixel-level PNG comparison for visual QA."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageChops


@dataclass(frozen=True)
class DiffBandRegion:
    """Changed-pixel ratio for one vertical screen band."""

    name: str
    changed_ratio: float
    y_start: int
    y_end: int


@dataclass(frozen=True)
class PixelDiffResult:
    """Outcome of a pixel differential comparison."""

    reference_path: str
    actual_path: str
    width: int
    height: int
    changed_pixels: int
    total_pixels: int
    changed_ratio: float
    threshold: float
    diff_bands: tuple[DiffBandRegion, ...] = ()

    @property
    def passed(self) -> bool:
        """Return True when changed pixel ratio is within ``threshold``."""
        return self.changed_ratio <= self.threshold


def _load_rgba(path: str) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGBA")


def resize_to_match(reference: Image.Image, actual: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Resize ``reference`` to the pixel dimensions of ``actual`` when they differ."""
    if reference.size == actual.size:
        return reference, actual
    resized = reference.resize(actual.size, Image.Resampling.LANCZOS)
    return resized, actual


def compare_png_files(
    reference_path: str,
    actual_path: str,
    *,
    threshold: float = 0.05,
    channel_tolerance: int = 16,
    resize_reference: bool = True,
) -> PixelDiffResult:
    """Compare two PNG images and return a pixel differential report.

    Args:
        reference_path: Baseline PNG (for example Figma export).
        actual_path: Candidate PNG (for example Flutter golden).
        threshold: Maximum allowed ratio of changed pixels (0.05 = 5%).
        channel_tolerance: Per-channel absolute difference treated as equal.
        resize_reference: When True, scale reference to actual size before diff.

    Returns:
        ``PixelDiffResult`` with pass/fail via ``passed``.
    """
    reference = _load_rgba(reference_path)
    actual = _load_rgba(actual_path)
    if resize_reference:
        reference, actual = resize_to_match(reference, actual)
    if reference.size != actual.size:
        msg = f"Image size mismatch after resize: reference={reference.size} actual={actual.size}"
        raise ValueError(msg)

    diff = ImageChops.difference(reference, actual)
    width, height = diff.size
    total_pixels = width * height
    changed_pixels = 0
    pixels = diff.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if max(red, green, blue, alpha) > channel_tolerance:
                changed_pixels += 1

    changed_ratio = changed_pixels / total_pixels if total_pixels else 0.0
    diff_bands = compute_vertical_diff_bands(
        reference,
        actual,
        channel_tolerance=channel_tolerance,
    )
    return PixelDiffResult(
        reference_path=reference_path,
        actual_path=actual_path,
        width=width,
        height=height,
        changed_pixels=changed_pixels,
        total_pixels=total_pixels,
        changed_ratio=changed_ratio,
        threshold=threshold,
        diff_bands=diff_bands,
    )


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
    """Split the diff into vertical bands and compute changed-pixel ratios.

    Args:
        reference: Baseline RGBA image resized to ``actual`` size.
        actual: Candidate RGBA image.
        channel_tolerance: Per-channel absolute difference treated as equal.
        band_count: Number of horizontal bands (default: top/middle/bottom).

    Returns:
        Tuple of band summaries ordered from top to bottom.
    """
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


def render_visual_diff_heatmap_png(
    reference_png: bytes,
    actual_png: bytes,
    *,
    channel_tolerance: int = 16,
    resize_reference: bool = True,
    overlay_alpha: int = 160,
) -> bytes:
    """Build a Figma-aligned heatmap PNG highlighting pixels that differ from the render.

    Mismatched pixels are tinted red on top of the reference (IMAGE 1) so the model can
    map error zones back to the target layout.

    Args:
        reference_png: Baseline PNG bytes (Figma export).
        actual_png: Candidate PNG bytes (Flutter render).
        channel_tolerance: Per-channel difference treated as equal.
        resize_reference: When True, scale reference to actual size before diff.
        overlay_alpha: Alpha for the red mismatch overlay (0-255).

    Returns:
        PNG bytes suitable for LLM visual refine attachment as IMAGE 3.
    """
    reference = Image.open(BytesIO(reference_png)).convert("RGBA")
    actual = Image.open(BytesIO(actual_png)).convert("RGBA")
    if resize_reference:
        reference, actual = resize_to_match(reference, actual)
    if reference.size != actual.size:
        msg = f"Image size mismatch after resize: reference={reference.size} actual={actual.size}"
        raise ValueError(msg)

    diff = ImageChops.difference(reference, actual)
    heatmap = reference.copy()
    diff_pixels = diff.load()
    out_pixels = heatmap.load()
    assert diff_pixels is not None and out_pixels is not None
    width, height = diff.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = diff_pixels[x, y]
            if max(red, green, blue, alpha) <= channel_tolerance:
                continue
            base = out_pixels[x, y]
            blend = overlay_alpha / 255.0
            out_pixels[x, y] = (
                int(base[0] * (1 - blend) + 255 * blend),
                int(base[1] * (1 - blend)),
                int(base[2] * (1 - blend)),
                base[3],
            )

    buffer = BytesIO()
    heatmap.save(buffer, format="PNG")
    return buffer.getvalue()
