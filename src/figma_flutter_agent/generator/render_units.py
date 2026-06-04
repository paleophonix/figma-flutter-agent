"""Figma-to-Flutter rendering unit conversions (FID-40/41/45).

Calibration table (CSS stdDev model, spike target FID-40):
- drop-shadow: ``figma_blur_to_flutter_blur_radius(B) ≈ 0.87·B − 0.87`` when B≥2
- ImageFilter: ``figma_blur_to_image_sigma(B) = B/2`` (matches CSS feGaussianBlur stdDev)
"""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal, round_geometry

# Flutter BoxShadow: convertRadiusToSigma(r) = r * 0.57735 + 0.5
_FLUTTER_SIGMA_FACTOR = 0.57735
_FLUTTER_SIGMA_OFFSET = 0.5

# Target comparison device pixel ratio for hairline snapping (FID-45).
DEFAULT_COMPARISON_DPR = 3.0


def figma_blur_to_flutter_blur_radius(figma_blur: float) -> float:
    """Map Figma/CSS shadow blur to Flutter ``BoxShadow.blurRadius``.

    Flutter draws Gaussian blur with ``sigma = convertRadiusToSigma(blurRadius)``.
    Figma drop shadows align with CSS ``box-shadow`` where stdDev ≈ ``figma_blur / 2``.

    Args:
        figma_blur: Visible blur radius from Figma ``DROP_SHADOW`` / ``INNER_SHADOW``.

    Returns:
        Calibrated Flutter ``blurRadius`` in logical pixels.
    """
    if figma_blur <= 0:
        return 0.0
    target_sigma = figma_blur / 2.0
    radius = (target_sigma - _FLUTTER_SIGMA_OFFSET) / _FLUTTER_SIGMA_FACTOR
    return max(0.0, round_geometry(radius) or 0.0)


def figma_blur_to_image_sigma(figma_blur: float) -> float:
    """Map Figma layer/background blur to ``ImageFilter.blur`` sigma.

    Args:
        figma_blur: Blur radius from Figma ``LAYER_BLUR`` or ``BACKGROUND_BLUR``.

    Returns:
        Sigma for ``ImageFilter.blur(sigmaX:, sigmaY:)``.
    """
    if figma_blur <= 0:
        return 0.0
    return max(1.0, round_geometry(figma_blur / 2.0) or 1.0)


def figma_spread_to_flutter_spread(figma_spread: float) -> float:
    """Map Figma shadow spread to Flutter ``BoxShadow.spreadRadius``.

    Args:
        figma_spread: Spread from Figma shadow effect.

    Returns:
        Flutter spread radius (pass-through until empirical spread model lands).
    """
    return round_geometry(figma_spread) or 0.0


def format_figma_blur_radius_literal(figma_blur: float) -> str:
    """Format calibrated ``BoxShadow.blurRadius`` for Dart emit."""
    return format_geometry_literal(figma_blur_to_flutter_blur_radius(figma_blur))


def format_figma_blur_sigma_literal(figma_blur: float) -> str:
    """Format calibrated ImageFilter sigma for Dart emit."""
    return format_geometry_literal(figma_blur_to_image_sigma(figma_blur))


def snap_to_device_pixel(value: float, *, dpr: float = DEFAULT_COMPARISON_DPR) -> float:
    """Snap a logical coordinate/size to the nearest physical pixel (FID-45).

    Args:
        value: Logical pixel value.
        dpr: Device pixel ratio for snapping.

    Returns:
        Snapped logical value.
    """
    if dpr <= 0:
        return value
    return round_geometry(round(value * dpr) / dpr) or value


def hairline_border_width(*, dpr: float = DEFAULT_COMPARISON_DPR) -> float:
    """Return a true 1-physical-pixel border width at ``dpr``."""
    if dpr <= 0:
        return 1.0
    return 1.0 / dpr
