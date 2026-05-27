"""Tests for visual diff heatmap rendering."""

from __future__ import annotations

from PIL import Image

from figma_flutter_agent.validation.pixeldiff import render_visual_diff_heatmap_png


def _solid_png(size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    from io import BytesIO

    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_render_visual_diff_heatmap_marks_changed_pixels() -> None:
    reference = _solid_png((4, 4), (255, 255, 255))
    actual = _solid_png((4, 4), (0, 0, 0))
    heatmap_png = render_visual_diff_heatmap_png(reference, actual, channel_tolerance=8)
    from io import BytesIO

    heatmap = Image.open(BytesIO(heatmap_png)).convert("RGBA")
    assert heatmap.getpixel((0, 0))[0] > 200
