"""Per-widget pixel diff scores using design-tree bounding boxes."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops

from figma_flutter_agent.schemas import CleanDesignTreeNode, StackPlacement

_CHANNEL_TOLERANCE = 16
_MIN_IOU_AREA = 64


@dataclass(frozen=True)
class WidgetDiffScore:
    """Changed-pixel ratio inside one widget bounding box."""

    node_id: str
    changed_ratio: float
    left: float
    top: float
    width: float
    height: float


def _design_canvas_size(root: CleanDesignTreeNode) -> tuple[float, float]:
    width = root.sizing.width or 414.0
    height = root.sizing.height or 896.0
    return float(width), float(height)


def _placement_box(
    placement: StackPlacement,
) -> tuple[float, float, float, float] | None:
    width = placement.width
    height = placement.height
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    return float(placement.left), float(placement.top), float(width), float(height)


def _scale_box(
    box: tuple[float, float, float, float],
    *,
    design_width: float,
    design_height: float,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    left, top, width, height = box
    scale_x = image_width / design_width if design_width else 1.0
    scale_y = image_height / design_height if design_height else 1.0
    x0 = max(0, int(left * scale_x))
    y0 = max(0, int(top * scale_y))
    x1 = min(image_width, int((left + width) * scale_x))
    y1 = min(image_height, int((top + height) * scale_y))
    return x0, y0, max(x1 - x0, 0), max(y1 - y0, 0)


def _count_changed_in_rect(
    diff: Image.Image,
    *,
    x0: int,
    y0: int,
    width: int,
    height: int,
    channel_tolerance: int,
) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        return 0, 0
    pixels = diff.load()
    assert pixels is not None
    changed = 0
    total = width * height
    for y in range(y0, y0 + height):
        for x in range(x0, x0 + width):
            red, green, blue, alpha = pixels[x, y]
            if max(red, green, blue, alpha) > channel_tolerance:
                changed += 1
    return changed, total


def compute_widget_diff_scores(
    reference_png: bytes,
    actual_png: bytes,
    clean_tree: CleanDesignTreeNode,
    *,
    channel_tolerance: int = _CHANNEL_TOLERANCE,
) -> list[WidgetDiffScore]:
    """Score visual diff density per widget bbox from the clean tree.

    Args:
        reference_png: Figma reference PNG bytes.
        actual_png: Flutter render PNG bytes.
        clean_tree: Screen clean tree with ``stackPlacement`` metadata.
        channel_tolerance: Per-channel diff tolerance (same as pixeldiff).

    Returns:
        Widget scores sorted by ``changed_ratio`` descending.
    """
    reference = Image.open(BytesIO(reference_png)).convert("RGBA")
    actual = Image.open(BytesIO(actual_png)).convert("RGBA")
    if reference.size != actual.size:
        reference = reference.resize(actual.size, Image.Resampling.LANCZOS)
    diff = ImageChops.difference(reference, actual)
    design_w, design_h = _design_canvas_size(clean_tree)
    image_w, image_h = actual.size

    scores: list[WidgetDiffScore] = []

    def walk(node: CleanDesignTreeNode) -> None:
        placement = node.stack_placement
        if placement is not None:
            box = _placement_box(placement)
            if box is not None:
                x0, y0, w, h = _scale_box(
                    box,
                    design_width=design_w,
                    design_height=design_h,
                    image_width=image_w,
                    image_height=image_h,
                )
                if w * h >= _MIN_IOU_AREA:
                    changed, total = _count_changed_in_rect(
                        diff,
                        x0=x0,
                        y0=y0,
                        width=w,
                        height=h,
                        channel_tolerance=channel_tolerance,
                    )
                    ratio = changed / total if total else 0.0
                    left, top, width, height = box
                    scores.append(
                        WidgetDiffScore(
                            node_id=node.id,
                            changed_ratio=ratio,
                            left=left,
                            top=top,
                            width=width,
                            height=height,
                        )
                    )
        for child in node.children:
            walk(child)

    walk(clean_tree)
    scores.sort(key=lambda item: item.changed_ratio, reverse=True)
    return scores


def select_surgical_targets(
    scores: list[WidgetDiffScore],
    *,
    min_changed_ratio: float = 0.08,
    max_widgets: int = 3,
) -> list[str]:
    """Pick Figma node ids that likely account for the visual diff.

    Args:
        scores: Per-widget diff scores (typically from ``compute_widget_diff_scores``).
        min_changed_ratio: Minimum in-bbox changed ratio to qualify.
        max_widgets: Maximum widgets to send to surgical refine.

    Returns:
        Node ids for surgical LLM patches.
    """
    targets: list[str] = []
    for score in scores:
        if score.changed_ratio < min_changed_ratio:
            continue
        targets.append(score.node_id)
        if len(targets) >= max_widgets:
            break
    return targets


def compute_diff_bounding_box(
    reference_png: bytes,
    actual_png: bytes,
    *,
    channel_tolerance: int = _CHANNEL_TOLERANCE,
) -> tuple[int, int, int, int] | None:
    """Return pixel bounding box ``(x0, y0, x1, y1)`` of changed regions, if any."""
    with tempfile.TemporaryDirectory(prefix="figma-flutter-iou-") as tmp:
        reference_path = Path(tmp) / "ref.png"
        actual_path = Path(tmp) / "act.png"
        reference_path.write_bytes(reference_png)
        actual_path.write_bytes(actual_png)
        reference = Image.open(reference_path).convert("RGBA")
        actual = Image.open(actual_path).convert("RGBA")
        if reference.size != actual.size:
            reference = reference.resize(actual.size, Image.Resampling.LANCZOS)
        diff = ImageChops.difference(reference, actual)
        pixels = diff.load()
        assert pixels is not None
        width, height = diff.size
        min_x, min_y = width, height
        max_x, max_y = -1, -1
        for y in range(height):
            for x in range(width):
                red, green, blue, alpha = pixels[x, y]
                if max(red, green, blue, alpha) > channel_tolerance:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        if max_x < 0:
            return None
        return min_x, min_y, max_x + 1, max_y + 1


def bbox_iou(
    a: tuple[int, int, int, int],
    b: tuple[float, float, float, float],
    *,
    design_width: float,
    design_height: float,
    image_width: int,
    image_height: int,
) -> float:
    """Intersection-over-union between a pixel diff box and a design-space widget box."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bw, bh = _scale_box(
        b,
        design_width=design_width,
        design_height=design_height,
        image_width=image_width,
        image_height=image_height,
    )
    bx1 = bx0 + bw
    by1 = by0 + bh
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    union = (ax1 - ax0) * (ay1 - ay0) + bw * bh - inter
    return inter / union if union > 0 else 0.0
