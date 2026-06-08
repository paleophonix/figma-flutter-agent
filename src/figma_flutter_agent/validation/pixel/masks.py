"""TEXT-region masking for pixel comparison."""

from __future__ import annotations

from collections.abc import Iterable

from PIL import Image, ImageDraw

from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.iou import _design_canvas_size
from figma_flutter_agent.validation.pixel.coordinates import figma_text_box, iter_text_nodes

MASK_FILL_RGBA = (0, 0, 0, 255)


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
        rect = figma_text_box(
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
    fill: tuple[int, int, int, int] = MASK_FILL_RGBA,
) -> Image.Image:
    """Stage 2 prep: paint TEXT bounding boxes solid black on a copy of ``image``."""
    masked = image.copy()
    draw = ImageDraw.Draw(masked)
    for x0, y0, x1, y1 in regions:
        draw.rectangle((x0, y0, x1, y1), fill=fill)
    return masked
