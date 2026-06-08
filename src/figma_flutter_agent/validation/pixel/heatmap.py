"""Visual diff heatmap rendering."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageChops

from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.pixel.compare import resize_to_match
from figma_flutter_agent.validation.pixel.masks import collect_text_mask_rects, mask_text_regions


def render_visual_diff_heatmap_png(
    reference_png: bytes,
    actual_png: bytes,
    *,
    channel_tolerance: int = 16,
    resize_reference: bool = True,
    overlay_alpha: int = 160,
    clean_tree: CleanDesignTreeNode | None = None,
) -> bytes:
    """Build a Figma-aligned heatmap PNG highlighting pixels that differ."""
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
