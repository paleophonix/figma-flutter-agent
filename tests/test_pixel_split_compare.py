"""Dual-channel pixel compare for corpus oracle."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
from figma_flutter_agent.validation.pixel.split_compare import compare_png_bytes_split


def _png_bytes(color: tuple[int, int, int, int], size: tuple[int, int] = (20, 20)) -> bytes:
    image = Image.new("RGBA", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_identical_images_zero_diff() -> None:
    tree = load_layout_tree("flex_summary_row")
    png = _png_bytes((10, 20, 30, 255), size=(390, 844))
    result = compare_png_bytes_split(
        png,
        png,
        clean_tree=tree,
        resize_reference=False,
    )
    assert result.non_text_pixel_diff == 0.0
    assert result.text_region_pixel_diff == 0.0
    assert result.passed_blocking


def test_structural_change_detected() -> None:
    tree = load_layout_tree("flex_summary_row")
    reference = _png_bytes((0, 0, 0, 255), size=(390, 844))
    act_img = Image.open(BytesIO(reference)).convert("RGBA")
    act_img.putpixel((380, 830), (255, 0, 0, 255))
    buf = BytesIO()
    act_img.save(buf, format="PNG")
    changed = buf.getvalue()

    result = compare_png_bytes_split(
        reference,
        changed,
        clean_tree=tree,
        non_text_pixel_max=0.05,
        resize_reference=False,
    )
    assert result.non_text_pixel_diff > 0.0
    assert result.non_text_pixel_diff < 0.05
    assert result.passed_blocking

    strict = compare_png_bytes_split(
        reference,
        changed,
        clean_tree=tree,
        non_text_pixel_max=0.0,
        resize_reference=False,
    )
    assert strict.non_text_pixel_diff > 0.0
    assert not strict.passed_blocking
