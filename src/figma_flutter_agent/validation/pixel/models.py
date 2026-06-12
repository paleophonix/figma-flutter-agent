"""Pixel comparison result models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


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


@dataclass(frozen=True)
class SplitPixelDiffResult:
    """Dual-channel pixel diff: structural (non-text) and text-region advisory."""

    non_text_pixel_diff: float
    text_region_pixel_diff: float
    text_bounds_delta: float
    non_text_pixel_max: float
    text_region_pixel_max: float
    text_bounds_delta_max: float
    text_validation_passed: bool

    @property
    def passed_blocking(self) -> bool:
        """Return True when structural pixel and text bounds gates pass."""
        return (
            self.text_validation_passed
            and self.non_text_pixel_diff <= self.non_text_pixel_max
            and self.text_bounds_delta <= self.text_bounds_delta_max
        )

    @property
    def passed_advisory(self) -> bool:
        """Return True when text-region pixel diff is within advisory tolerance."""
        return self.text_region_pixel_diff <= self.text_region_pixel_max


class FlutterCoordinateMapper(Protocol):
    """Runtime widget bounds keyed by Figma node id."""

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
