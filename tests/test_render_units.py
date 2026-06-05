"""Unit tests for Figma-to-Flutter rendering unit conversions (FID-40/41/45)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_style import _shadow_expr
from figma_flutter_agent.generator.render_units import (
    DEFAULT_COMPARISON_DPR,
    figma_blur_to_flutter_blur_radius,
    figma_blur_to_image_sigma,
    hairline_border_width,
    snap_to_device_pixel,
)
from figma_flutter_agent.schemas import ShadowEffect


def test_figma_blur_to_flutter_blur_radius_calibrated() -> None:
    # CSS stdDev model: sigma = figma_blur/2; invert Flutter convertRadiusToSigma.
    radius = figma_blur_to_flutter_blur_radius(24.0)
    assert 12.0 < radius < 21.0
    assert radius != 24.0


def test_figma_blur_to_image_sigma_half_radius() -> None:
    assert figma_blur_to_image_sigma(24.0) == 12.0
    assert figma_blur_to_image_sigma(0.0) == 0.0


def test_shadow_expr_uses_calibrated_blur_radius() -> None:
    effect = ShadowEffect(
        kind="drop",
        offset_x=0,
        offset_y=4,
        blur=24,
        spread=0,
        color="0x40000000",
    )
    expr = _shadow_expr(effect)
    assert "blurRadius: 24" not in expr
    assert "blurRadius:" in expr


def test_snap_to_device_pixel_at_dpr() -> None:
    snapped = snap_to_device_pixel(10.3333333, dpr=3.0)
    assert snapped == 10.3


def test_hairline_border_width() -> None:
    assert abs(hairline_border_width(dpr=DEFAULT_COMPARISON_DPR) - 1.0 / 3.0) < 1e-6
