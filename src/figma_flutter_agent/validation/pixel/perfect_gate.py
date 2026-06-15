"""Strict pixel-perfect oracle thresholds (Track A / A3)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.schemas.tree import CleanDesignTreeNode
from figma_flutter_agent.validation.pixel.models import SplitPixelDiffResult
from figma_flutter_agent.validation.pixel.split_compare import compare_png_bytes_split


@dataclass(frozen=True)
class PixelPerfectThresholdProfile:
    """Blocking thresholds for pixel-perfect gate mode."""

    non_text_pixel_max: float = 0.0
    text_region_pixel_max: float = 0.0
    text_bounds_delta_max: float = 0.0
    channel_tolerance: int = 2
    blocking_text_diff: bool = True


PIXEL_PERFECT_THRESHOLD_PROFILE = PixelPerfectThresholdProfile()


def compare_png_bytes_pixel_perfect(
    reference_png: bytes,
    actual_png: bytes,
    *,
    clean_tree: CleanDesignTreeNode,
    profile: PixelPerfectThresholdProfile = PIXEL_PERFECT_THRESHOLD_PROFILE,
    per_node_mask_ids: frozenset[str] | None = None,
) -> SplitPixelDiffResult:
    """Compare PNG bytes under strict pixel-perfect thresholds.

    Args:
        reference_png: Baseline PNG bytes.
        actual_png: Capture PNG bytes.
        clean_tree: Layout tree for masks and coordinate validation.
        profile: Strict threshold profile.
        per_node_mask_ids: Optional subset of TEXT node ids for masks.

    Returns:
        Dual-channel diff with blocking text-region checks when configured.
    """
    _ = per_node_mask_ids
    result = compare_png_bytes_split(
        reference_png,
        actual_png,
        clean_tree=clean_tree,
        non_text_pixel_max=profile.non_text_pixel_max,
        text_region_pixel_max=(
            profile.text_region_pixel_max
            if profile.blocking_text_diff
            else profile.non_text_pixel_max
        ),
        text_bounds_delta_max=profile.text_bounds_delta_max,
        channel_tolerance=profile.channel_tolerance,
    )
    return result


def passed_pixel_perfect_gate(result: SplitPixelDiffResult, *, blocking_text: bool) -> bool:
    """Return True when diff metrics satisfy pixel-perfect blocking rules."""
    if not result.passed_blocking:
        return False
    if blocking_text:
        return result.text_region_pixel_diff <= result.text_region_pixel_max
    return True
