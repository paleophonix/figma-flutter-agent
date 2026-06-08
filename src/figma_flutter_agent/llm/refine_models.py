"""Visual refine focus and attempt models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RefineFocus = Literal["interaction", "layout_spacing", "typography_color", "pixel_polish"]

_REFINE_FOCUS_SEQUENCE: tuple[RefineFocus, ...] = (
    "interaction",
    "layout_spacing",
    "typography_color",
    "pixel_polish",
)


@dataclass(frozen=True)
class RefineAttemptSummary:
    """Compact record of one visual refine attempt for the next LLM pass."""

    attempt: int
    changed_ratio: float
    outcome: str
    error_preview: str | None = None
    diff_regions: tuple[dict[str, Any], ...] = ()
    excluded_surgical_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        """Serialize for the visual-refine JSON user payload."""
        payload: dict[str, Any] = {
            "attempt": self.attempt,
            "changedRatio": self.changed_ratio,
            "outcome": self.outcome,
        }
        if self.error_preview:
            payload["errorPreview"] = self.error_preview
        if self.diff_regions:
            payload["diffRegions"] = list(self.diff_regions)
        if self.excluded_surgical_ids:
            payload["excludedSurgicalIds"] = list(self.excluded_surgical_ids)
        return payload


def resolve_refine_focus(*, attempt: int, max_attempts: int) -> RefineFocus:
    """Return the single focus area for a visual refine attempt."""
    if max_attempts <= 1:
        return "interaction"
    index = min(max(attempt - 1, 0), len(_REFINE_FOCUS_SEQUENCE) - 1)
    if attempt >= max_attempts and max_attempts >= 3:
        return "pixel_polish"
    return _REFINE_FOCUS_SEQUENCE[index]
