"""PNG pixel comparison and TEXT-masked comparison."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.pixel.bands import compute_vertical_diff_bands
from figma_flutter_agent.validation.pixel.coordinates import validate_text_coordinates
from figma_flutter_agent.validation.pixel.masks import collect_text_mask_rects, mask_text_regions
from figma_flutter_agent.validation.pixel.models import (
    FlutterCoordinateMapper,
    PixelDiffResult,
    VisualCompareResult,
)


def _load_rgba(path: str) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGBA")


def resize_to_match(reference: Image.Image, actual: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Resize ``reference`` to the pixel dimensions of ``actual`` when they differ."""
    if reference.size == actual.size:
        return reference, actual
    resized = reference.resize(actual.size, Image.Resampling.LANCZOS)
    return resized, actual


def compare_rgba_images(
    reference: Image.Image,
    actual: Image.Image,
    *,
    reference_path: str,
    actual_path: str,
    threshold: float,
    channel_tolerance: int,
) -> PixelDiffResult:
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


def compare_png_files(
    reference_path: str,
    actual_path: str,
    *,
    threshold: float = 0.05,
    channel_tolerance: int = 16,
    resize_reference: bool = True,
) -> PixelDiffResult:
    """Compare two PNG images and return a pixel differential report."""
    reference = _load_rgba(reference_path)
    actual = _load_rgba(actual_path)
    if resize_reference:
        reference, actual = resize_to_match(reference, actual)
    return compare_rgba_images(
        reference,
        actual,
        reference_path=reference_path,
        actual_path=actual_path,
        threshold=threshold,
        channel_tolerance=channel_tolerance,
    )


def compare_png_files_with_text_mask(
    reference_path: str,
    actual_path: str,
    *,
    clean_tree: CleanDesignTreeNode,
    flutter_mapper: FlutterCoordinateMapper | None = None,
    threshold: float = 0.005,
    text_coordinate_tolerance: int = 3,
    channel_tolerance: int = 16,
    resize_reference: bool = True,
) -> VisualCompareResult:
    """Two-stage compare: TEXT coordinate contract, then masked pixel diff."""
    reference = _load_rgba(reference_path)
    actual = _load_rgba(actual_path)
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
    if not text_validation.passed:
        placeholder = PixelDiffResult(
            reference_path=reference_path,
            actual_path=actual_path,
            width=image_width,
            height=image_height,
            changed_pixels=image_width * image_height,
            total_pixels=image_width * image_height,
            changed_ratio=1.0,
            threshold=threshold,
        )
        return VisualCompareResult(pixel=placeholder, text_validation=text_validation)

    mask_rects = collect_text_mask_rects(
        clean_tree,
        image_width=image_width,
        image_height=image_height,
    )
    if mask_rects:
        reference = mask_text_regions(reference, mask_rects)
        actual = mask_text_regions(actual, mask_rects)

    pixel = compare_rgba_images(
        reference,
        actual,
        reference_path=reference_path,
        actual_path=actual_path,
        threshold=threshold,
        channel_tolerance=channel_tolerance,
    )
    return VisualCompareResult(pixel=pixel, text_validation=text_validation)


def compare_png_bytes_with_text_mask(
    reference_png: bytes,
    actual_png: bytes,
    *,
    clean_tree: CleanDesignTreeNode,
    flutter_mapper: FlutterCoordinateMapper | None = None,
    threshold: float = 0.005,
    text_coordinate_tolerance: int = 3,
    channel_tolerance: int = 16,
) -> VisualCompareResult:
    """In-memory two-stage compare for visual refine."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="figma-flutter-pixeldiff-") as tmp:
        reference_path = Path(tmp) / "reference.png"
        actual_path = Path(tmp) / "actual.png"
        reference_path.write_bytes(reference_png)
        actual_path.write_bytes(actual_png)
        return compare_png_files_with_text_mask(
            reference_path.as_posix(),
            actual_path.as_posix(),
            clean_tree=clean_tree,
            flutter_mapper=flutter_mapper,
            threshold=threshold,
            text_coordinate_tolerance=text_coordinate_tolerance,
            channel_tolerance=channel_tolerance,
            resize_reference=True,
        )
