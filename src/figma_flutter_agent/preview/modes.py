"""Capture mode and backend identifiers for preview vs oracle paths."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from figma_flutter_agent.config import Settings


class CaptureMode(StrEnum):
    """High-level capture intent: Flutter web PNG or oracle with Figma diff."""

    PREVIEW = "preview"
    ORACLE = "oracle"


class CaptureBackend(StrEnum):
    """Concrete runtime used to produce a capture PNG."""

    BROWSER_PREVIEW = "browser_preview"
    FLUTTER_TEST = "flutter_test"


def resolve_capture_mode(settings: Settings) -> CaptureMode:
    """Return configured capture mode for wizard run/view and pipeline debug capture."""
    return CaptureMode(settings.agent.runtime.default_capture_mode)
