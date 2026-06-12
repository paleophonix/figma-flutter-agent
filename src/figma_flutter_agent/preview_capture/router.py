"""Capture mode router with hard preview/oracle separation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from figma_flutter_agent.preview_capture.capture import capture_preview_png
from figma_flutter_agent.preview_capture.models import PreviewCaptureRequest, PreviewCaptureResult
from figma_flutter_agent.preview_capture.modes import CaptureMode

if TYPE_CHECKING:
    from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult


def assert_preview_mode(mode: CaptureMode) -> None:
    """Raise when a preview-only code path receives oracle mode."""
    if mode is not CaptureMode.PREVIEW:
        msg = f"Expected capture mode {CaptureMode.PREVIEW.value}, got {mode.value}"
        raise ValueError(msg)


def capture_with_mode(
    *,
    mode: CaptureMode,
    preview_request: PreviewCaptureRequest | None = None,
    oracle_kwargs: dict[str, Any] | None = None,
) -> PreviewCaptureResult | GoldenCaptureResult:
    """Dispatch capture by explicit mode without preview→oracle fallback.

    Args:
        mode: Preview or oracle capture mode.
        preview_request: Required when ``mode`` is preview.
        oracle_kwargs: Keyword arguments for ``capture_planned_flutter_golden_png``.

    Returns:
        Preview or golden capture result for the selected mode.

    Raises:
        FastPreviewUnavailableError: Preview backend unavailable (no oracle fallback).
        ValueError: Missing request payload for the selected mode.
    """
    if mode is CaptureMode.PREVIEW:
        if preview_request is None:
            msg = "preview_request is required for preview capture mode"
            raise ValueError(msg)
        return capture_preview_png(preview_request)

    if oracle_kwargs is None:
        msg = "oracle_kwargs is required for oracle capture mode"
        raise ValueError(msg)

    from figma_flutter_agent.validation.golden_capture.capture import (
        capture_planned_flutter_golden_png,
    )

    return capture_planned_flutter_golden_png(**oracle_kwargs)


def preview_backend_label() -> str:
    """Return resolved preview backend label for doctor output."""
    from figma_flutter_agent.preview_capture.browser import (
        find_chrome_executable,
        playwright_available,
    )

    if playwright_available():
        return "playwright"
    if find_chrome_executable() is not None:
        return "chrome"
    return "unavailable"
