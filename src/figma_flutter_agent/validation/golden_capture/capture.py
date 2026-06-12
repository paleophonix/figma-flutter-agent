"""Golden capture entry point dispatching to host or Docker runtimes."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.golden_capture.capture_docker import (
    _ensure_docker_golden_image,
    capture_planned_flutter_golden_png_docker,
)
from figma_flutter_agent.validation.golden_capture.capture_host import (
    CAPTURE_KEYS_OUT_ENV,
    CAPTURE_OUT_ENV,
    GoldenCaptureHostSession,
    _resolve_host_capture_test,
)
from figma_flutter_agent.validation.golden_capture.capture_host_run import (
    capture_planned_flutter_golden_png_host,
)
from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult
from figma_flutter_agent.validation.golden_runtime import (
    GoldenCaptureMode,
    resolve_golden_runtime,
)

__all__ = [
    "CAPTURE_KEYS_OUT_ENV",
    "CAPTURE_OUT_ENV",
    "GoldenCaptureHostSession",
    "GoldenCaptureResult",
    "_ensure_docker_golden_image",
    "_resolve_host_capture_test",
    "capture_planned_flutter_golden_png",
    "capture_planned_flutter_golden_png_docker",
    "capture_planned_flutter_golden_png_host",
    "resolve_flutter_executable",
]


def capture_planned_flutter_golden_png(
    planned: dict[str, str],
    *,
    feature_name: str,
    flutter_sdk: str | Path | None = None,
    project_dir: Path | None = None,
    golden_runtime: GoldenCaptureMode | None = None,
    settings: Settings | None = None,
    no_docker: bool = False,
    layout_tree: CleanDesignTreeNode | None = None,
    host_session: GoldenCaptureHostSession | None = None,
    capture_in_project: bool = True,
    timings: object | None = None,
) -> GoldenCaptureResult:
    """Capture a golden PNG using the resolved host or Docker runtime."""
    sdk_root = flutter_sdk
    if sdk_root is None and settings is not None:
        sdk_root = settings.flutter_sdk or None
    if flutter_sdk is not None:
        selection = resolve_golden_runtime("host", settings=settings, no_docker=True)
    else:
        selection = resolve_golden_runtime(
            golden_runtime,
            settings=settings,
            no_docker=no_docker,
        )
    if selection.fallback_from_docker and selection.configured in ("docker", "auto"):
        logger.warning(
            "Golden capture falling back to host runtime (configured={})",
            selection.configured,
        )
    if selection.runtime == "docker":
        image_failure = _ensure_docker_golden_image(settings)
        if image_failure is not None:
            return image_failure
        return capture_planned_flutter_golden_png_docker(
            planned,
            feature_name=feature_name,
            project_dir=project_dir,
            layout_tree=layout_tree,
        )
    return capture_planned_flutter_golden_png_host(
        planned,
        feature_name=feature_name,
        flutter_sdk=sdk_root,
        project_dir=project_dir,
        layout_tree=layout_tree,
        settings=settings,
        host_session=host_session,
        capture_in_project=capture_in_project,
        timings=timings,  # type: ignore[arg-type]
    )
