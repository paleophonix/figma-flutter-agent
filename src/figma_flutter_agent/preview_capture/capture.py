"""Fast browser preview capture entry point."""

from __future__ import annotations

import time

from loguru import logger

from figma_flutter_agent.errors import FastPreviewUnavailableError
from figma_flutter_agent.preview_capture.browser import capture_scene_png
from figma_flutter_agent.preview_capture.models import PreviewCaptureRequest, PreviewCaptureResult
from figma_flutter_agent.preview_capture.modes import CaptureBackend, CaptureMode


def capture_preview_png(request: PreviewCaptureRequest) -> PreviewCaptureResult:
    """Capture a browser preview PNG without invoking Flutter tooling.

    Args:
        request: Preview capture request with scene and optional output path.

    Returns:
        Capture result with PNG bytes or a failure reason.

    Raises:
        FastPreviewUnavailableError: When the browser backend is unavailable.
    """
    started = time.monotonic()
    image_nodes = sum(1 for node in request.scene.nodes if node.type == "image")
    try:
        png, backend = capture_scene_png(
            request.scene,
            timeout_sec=request.timeout_sec,
            device_scale_factor=request.device_scale_factor,
        )
    except FastPreviewUnavailableError:
        logger.exception(
            "capture_mode={} backend={} screen={} failed=backend_unavailable",
            CaptureMode.PREVIEW.value,
            CaptureBackend.BROWSER_PREVIEW.value,
            request.screen_id or "-",
        )
        raise

    elapsed = time.monotonic() - started
    if request.output_path is not None:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(png)

    logger.info(
        "capture_mode={} backend={} screen={} nodes={} image_nodes={} elapsed={:.2f}s png_bytes={}",
        CaptureMode.PREVIEW.value,
        backend,
        request.screen_id or "-",
        len(request.scene.nodes),
        image_nodes,
        elapsed,
        len(png),
    )
    return PreviewCaptureResult(
        png=png,
        elapsed_sec=elapsed,
        backend=backend,
    )
