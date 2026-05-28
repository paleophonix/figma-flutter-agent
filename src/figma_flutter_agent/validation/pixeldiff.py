"""Pixel-level PNG comparison for visual QA."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from PIL import Image, ImageChops, ImageDraw

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.validation.iou import (
    _design_canvas_size,
    _placement_box,
    _scale_box,
)

_MASK_FILL_RGBA = (0, 0, 0, 255)


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


@dataclass(frozen=True)
class TextCoordinateFailure:
    """One TEXT node that failed the coordinate contract."""

    node_id: str
    expected_left: float
    expected_top: float
    actual_left: float | None
    actual_top: float | None
    delta_x: float
    delta_y: float

    def repair_message(self) -> str:
        """Return a single-line message for LLM repair / warnings."""
        found_top = "missing" if self.actual_top is None else f"{self.actual_top:g}"
        return (
            f"Text node [{self.node_id}] layout displacement detected. "
            f"Expected top: {self.expected_top:g}, found: {found_top}"
        )


@dataclass(frozen=True)
class TextCoordinateValidationResult:
    """Outcome of stage-1 TEXT bounding-box validation."""

    passed: bool
    failures: tuple[TextCoordinateFailure, ...] = ()

    @property
    def first_repair_message(self) -> str | None:
        """Return the first failure message when validation did not pass."""
        if self.passed or not self.failures:
            return None
        return self.failures[0].repair_message()


@dataclass(frozen=True)
class VisualCompareResult:
    """Pixel diff plus optional TEXT coordinate gate."""

    pixel: PixelDiffResult
    text_validation: TextCoordinateValidationResult

    @property
    def passed(self) -> bool:
        """Return True when TEXT coordinates and pixel diff both pass."""
        return self.text_validation.passed and self.pixel.passed


class FlutterCoordinateMapper(Protocol):
    """Runtime widget bounds keyed by Figma node id (``ElementCoordinateMapper`` output)."""

    def rect_for_node_id(self, node_id: str) -> tuple[float, float, float, float] | None:
        """Return ``(left, top, width, height)`` in render pixel space."""
        ...


@dataclass(frozen=True)
class DictFlutterCoordinateMapper:
    """In-memory mapper built from golden capture JSON."""

    rects_by_token: Mapping[str, tuple[float, float, float, float]]

    def rect_for_node_id(self, node_id: str) -> tuple[float, float, float, float] | None:
        """Look up bounds by node id or ``figma-`` token suffix."""
        candidates = (
            node_id,
            node_id.replace(":", "_"),
            node_id.removeprefix("figma-"),
        )
        for key in candidates:
            bounds = self.rects_by_token.get(key)
            if bounds is not None:
                return bounds
        return None


def parse_flutter_mapper_payload(
    payload: Mapping[str, object] | None,
) -> DictFlutterCoordinateMapper | None:
    """Build a mapper from ``{token: {left, top, width, height}}`` golden JSON."""
    if not payload:
        return None
    rects: dict[str, tuple[float, float, float, float]] = {}
    for token, raw in payload.items():
        if not isinstance(raw, Mapping):
            continue
        try:
            rects[str(token)] = (
                float(raw["left"]),
                float(raw["top"]),
                float(raw["width"]),
                float(raw["height"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not rects:
        return None
    return DictFlutterCoordinateMapper(rects_by_token=rects)


def iter_text_nodes(root: CleanDesignTreeNode) -> Iterable[CleanDesignTreeNode]:
    """Yield TEXT nodes in depth-first order."""
    if root.type == NodeType.TEXT:
        yield root
    for child in root.children:
        yield from iter_text_nodes(child)


def _figma_text_box(
    node: CleanDesignTreeNode,
    *,
    design_width: float,
    design_height: float,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int] | None:
    placement = node.stack_placement
    if placement is None:
        return None
    box = _placement_box(placement)
    if box is None:
        return None
    x0, y0, width, height = _scale_box(
        box,
        design_width=design_width,
        design_height=design_height,
        image_width=image_width,
        image_height=image_height,
    )
    if width <= 0 or height <= 0:
        return None
    return x0, y0, x0 + width, y0 + height


def validate_text_coordinates(
    clean_tree: CleanDesignTreeNode,
    flutter_mapper: FlutterCoordinateMapper | None,
    *,
    tolerance: int,
    image_width: int,
    image_height: int,
) -> TextCoordinateValidationResult:
    """Stage 1: compare TEXT node top-left corners before pixel diff.

    Args:
        clean_tree: Parsed clean design tree (``figma_tree``).
        flutter_mapper: Runtime bounds from golden capture; when ``None``, stage passes.
        tolerance: Maximum allowed ``|delta|`` in pixels for X and Y.
        image_width: Render width used to scale Figma design coordinates.
        image_height: Render height used to scale Figma design coordinates.

    Returns:
        Validation result; failures include LLM-ready repair messages.
    """
    if flutter_mapper is None:
        return TextCoordinateValidationResult(passed=True)

    design_w, design_h = _design_canvas_size(clean_tree)
    failures: list[TextCoordinateFailure] = []
    tol = float(tolerance)

    for node in iter_text_nodes(clean_tree):
        figma_rect = _figma_text_box(
            node,
            design_width=design_w,
            design_height=design_h,
            image_width=image_width,
            image_height=image_height,
        )
        if figma_rect is None:
            continue
        figma_left = float(figma_rect[0])
        figma_top = float(figma_rect[1])
        flutter_bounds = flutter_mapper.rect_for_node_id(node.id)
        if flutter_bounds is None:
            continue
        flutter_left, flutter_top, _, _ = flutter_bounds
        delta_x = abs(figma_left - flutter_left)
        delta_y = abs(figma_top - flutter_top)
        if delta_x > tol or delta_y > tol:
            failures.append(
                TextCoordinateFailure(
                    node_id=node.id,
                    expected_left=figma_left,
                    expected_top=figma_top,
                    actual_left=flutter_left,
                    actual_top=flutter_top,
                    delta_x=delta_x,
                    delta_y=delta_y,
                )
            )

    return TextCoordinateValidationResult(
        passed=not failures,
        failures=tuple(failures),
    )


def collect_text_mask_rects(
    clean_tree: CleanDesignTreeNode,
    *,
    image_width: int,
    image_height: int,
) -> tuple[tuple[int, int, int, int], ...]:
    """Collect pixel rectangles to mask for all TEXT nodes with stack placement."""
    design_w, design_h = _design_canvas_size(clean_tree)
    regions: list[tuple[int, int, int, int]] = []
    for node in iter_text_nodes(clean_tree):
        rect = _figma_text_box(
            node,
            design_width=design_w,
            design_height=design_h,
            image_width=image_width,
            image_height=image_height,
        )
        if rect is not None:
            regions.append(rect)
    return tuple(regions)


def mask_text_regions(
    image: Image.Image,
    regions: Iterable[tuple[int, int, int, int]],
    *,
    fill: tuple[int, int, int, int] = _MASK_FILL_RGBA,
) -> Image.Image:
    """Stage 2 prep: paint TEXT bounding boxes solid black on a copy of ``image``."""
    masked = image.copy()
    draw = ImageDraw.Draw(masked)
    for x0, y0, x1, y1 in regions:
        draw.rectangle((x0, y0, x1, y1), fill=fill)
    return masked


def _load_rgba(path: str) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGBA")


def resize_to_match(reference: Image.Image, actual: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Resize ``reference`` to the pixel dimensions of ``actual`` when they differ."""
    if reference.size == actual.size:
        return reference, actual
    resized = reference.resize(actual.size, Image.Resampling.LANCZOS)
    return resized, actual


def _compare_rgba_images(
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
    return _compare_rgba_images(
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
    """Two-stage compare: TEXT coordinate contract, then masked pixel diff.

    Args:
        reference_path: Figma reference PNG path.
        actual_path: Flutter render PNG path.
        clean_tree: Design tree with TEXT ``stackPlacement`` metadata.
        flutter_mapper: Runtime widget bounds from golden capture.
        threshold: Maximum changed-pixel ratio after TEXT masking.
        text_coordinate_tolerance: Allowed top-left drift in pixels (stage 1).
        channel_tolerance: Per-channel tolerance for stage-2 diff.
        resize_reference: Scale reference to actual dimensions before diff.

    Returns:
        Combined validation and pixel diff result.
    """
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

    pixel = _compare_rgba_images(
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
    from pathlib import Path

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
    clean_tree: CleanDesignTreeNode | None = None,
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
        clean_tree: When set, TEXT regions are masked before diff (stage 2 only).

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

    if clean_tree is not None:
        mask_rects = collect_text_mask_rects(
            clean_tree,
            image_width=actual.size[0],
            image_height=actual.size[1],
        )
        if mask_rects:
            reference = mask_text_regions(reference, mask_rects)
            actual = mask_text_regions(actual, mask_rects)

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
