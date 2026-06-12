"""Dual-channel pixel comparison for corpus oracle gates."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from figma_flutter_agent.schemas.tree import CleanDesignTreeNode
from figma_flutter_agent.validation.pixel.compare import (
    compare_rgba_images,
    resize_to_match,
)
from figma_flutter_agent.validation.pixel.coordinates import validate_text_coordinates
from figma_flutter_agent.validation.pixel.masks import collect_text_mask_rects, mask_text_regions
from figma_flutter_agent.validation.pixel.models import (
    FlutterCoordinateMapper,
    SplitPixelDiffResult,
    TextCoordinateFailure,
)


def _load_rgba_from_bytes(png: bytes) -> Image.Image:
    with Image.open(BytesIO(png)) as image:
        return image.convert("RGBA")


def _max_text_bounds_delta(failures: tuple[TextCoordinateFailure, ...]) -> float:
    if not failures:
        return 0.0
    return float(max(max(abs(item.delta_x), abs(item.delta_y)) for item in failures))


def _diff_ratio_outside_mask(
    reference: Image.Image,
    actual: Image.Image,
    mask_rects: tuple[tuple[int, int, int, int], ...],
    *,
    channel_tolerance: int,
) -> float:
    """Changed-pixel ratio excluding TEXT mask rectangles."""
    if not mask_rects:
        return compare_rgba_images(
            reference,
            actual,
            reference_path="reference",
            actual_path="actual",
            threshold=1.0,
            channel_tolerance=channel_tolerance,
        ).changed_ratio

    ref = reference.copy()
    act = actual.copy()
    ref = mask_text_regions(ref, mask_rects)
    act = mask_text_regions(act, mask_rects)
    return compare_rgba_images(
        ref,
        act,
        reference_path="reference",
        actual_path="actual",
        threshold=1.0,
        channel_tolerance=channel_tolerance,
    ).changed_ratio


def _diff_ratio_inside_mask(
    reference: Image.Image,
    actual: Image.Image,
    mask_rects: tuple[tuple[int, int, int, int], ...],
    *,
    channel_tolerance: int,
) -> float:
    """Changed-pixel ratio inside TEXT mask rectangles only."""
    if not mask_rects:
        return 0.0

    width, height = actual.size
    ref_blank = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    act_blank = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    ref_inside = mask_text_regions(ref_blank, mask_rects, fill=(0, 0, 0, 0))
    act_inside = mask_text_regions(act_blank, mask_rects, fill=(0, 0, 0, 0))

    for x0, y0, x1, y1 in mask_rects:
        region_ref = reference.crop((x0, y0, x1, y1))
        region_act = actual.crop((x0, y0, x1, y1))
        ref_inside.paste(region_ref, (x0, y0))
        act_inside.paste(region_act, (x0, y0))

    return compare_rgba_images(
        ref_inside,
        act_inside,
        reference_path="reference_text",
        actual_path="actual_text",
        threshold=1.0,
        channel_tolerance=channel_tolerance,
    ).changed_ratio


def compare_png_bytes_split(
    reference_png: bytes,
    actual_png: bytes,
    *,
    clean_tree: CleanDesignTreeNode,
    flutter_mapper: FlutterCoordinateMapper | None = None,
    non_text_pixel_max: float = 0.05,
    text_region_pixel_max: float = 0.15,
    text_bounds_delta_max: float = 3.0,
    text_coordinate_tolerance: int = 3,
    channel_tolerance: int = 16,
    resize_reference: bool = False,
) -> SplitPixelDiffResult:
    """Compare PNG bytes with separate structural and text-region channels.

    Args:
        reference_png: Baseline PNG bytes.
        actual_png: Fresh capture PNG bytes.
        clean_tree: Layout tree for TEXT mask and coordinate validation.
        flutter_mapper: Optional runtime bounds mapper.
        non_text_pixel_max: Blocking threshold for non-text pixels.
        text_region_pixel_max: Advisory threshold for text-region pixels.
        text_bounds_delta_max: Blocking max TEXT coordinate delta.
        text_coordinate_tolerance: Per-axis tolerance for text coordinates.
        channel_tolerance: Per-channel RGBA tolerance for pixel diff.
        resize_reference: When True, resize reference to match actual dimensions.

    Returns:
        Dual-channel diff metrics with pass helpers.
    """
    reference = _load_rgba_from_bytes(reference_png)
    actual = _load_rgba_from_bytes(actual_png)
    if resize_reference:
        reference, actual = resize_to_match(reference, actual)

    image_width, image_height = actual.size
    text_validation = validate_text_coordinates(
        clean_tree,
        flutter_mapper,
        tolerance=text_coordinate_tolerance,
        image_width=image_width,
        image_height=image_height,
    )
    mask_rects = collect_text_mask_rects(
        clean_tree,
        image_width=image_width,
        image_height=image_height,
    )

    non_text_diff = _diff_ratio_outside_mask(
        reference,
        actual,
        mask_rects,
        channel_tolerance=channel_tolerance,
    )
    text_region_diff = _diff_ratio_inside_mask(
        reference,
        actual,
        mask_rects,
        channel_tolerance=channel_tolerance,
    )
    bounds_delta = _max_text_bounds_delta(text_validation.failures)

    return SplitPixelDiffResult(
        non_text_pixel_diff=non_text_diff,
        text_region_pixel_diff=text_region_diff,
        text_bounds_delta=bounds_delta,
        non_text_pixel_max=non_text_pixel_max,
        text_region_pixel_max=text_region_pixel_max,
        text_bounds_delta_max=text_bounds_delta_max,
        text_validation_passed=text_validation.passed,
    )
