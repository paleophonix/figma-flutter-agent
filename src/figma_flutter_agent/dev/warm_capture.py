"""Persistent warm sandbox for fast iterative Flutter screen PNG capture.

Compiles only a minimal skeleton plus the planned screen/layout (not the full
customer app). Reuses ``GoldenCaptureHostSession`` across wizard/agent runs so
``flutter test`` incremental builds apply after the first cold compile.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.golden_capture.capture import capture_planned_flutter_golden_png
from figma_flutter_agent.validation.golden_capture.capture_host import (
    GoldenCaptureHostSession,
    _resolve_host_capture_test,
)
from figma_flutter_agent.validation.golden_capture.project import (
    _copy_skeleton_project,
    _run_flutter_pub_get,
    _sandbox_needs_skeleton_resync,
    _write_skeleton_fingerprint_stamp,
)
from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult
from figma_flutter_agent.validation.golden_capture.warm_runtime import GoldenCaptureTimings

_WARM_SESSIONS: dict[tuple[str, str], GoldenCaptureHostSession] = {}


def warm_capture_sandbox_dir(project_dir: Path) -> Path:
    """Return the on-disk warm capture workspace for a Flutter project."""
    from figma_flutter_agent.debug.migrate import ensure_project_debug_layout
    from figma_flutter_agent.debug.paths import capture_sandbox_dir

    ensure_project_debug_layout(project_dir)
    return capture_sandbox_dir(project_dir)


def reset_warm_capture_session(project_dir: Path, feature_name: str) -> None:
    """Drop a cached warm session (for example after ``flutter clean``)."""
    key = _session_key(project_dir, feature_name)
    session = _WARM_SESSIONS.pop(key, None)
    if session is not None:
        session.close()


def _session_key(project_dir: Path, feature_name: str) -> tuple[str, str]:
    return (project_dir.expanduser().resolve().as_posix(), feature_name)


def _ensure_sandbox_bootstrapped(
    capture_dir: Path,
    *,
    flutter: str,
    timings: GoldenCaptureTimings | None = None,
) -> GoldenCaptureResult | None:
    import time

    if _sandbox_needs_skeleton_resync(capture_dir):
        bootstrap_started = time.monotonic()
        capture_dir.parent.mkdir(parents=True, exist_ok=True)
        if capture_dir.is_dir():
            import shutil

            shutil.rmtree(capture_dir)
        _copy_skeleton_project(capture_dir)
        _write_skeleton_fingerprint_stamp(capture_dir)
        logger.info("Bootstrapping warm capture sandbox at {}", capture_dir.as_posix())
        if timings is not None:
            timings.add("prepareWorkspace", time.monotonic() - bootstrap_started)
    return _run_flutter_pub_get(capture_dir, flutter, timings=timings)


def get_or_create_warm_session(
    project_dir: Path,
    feature_name: str,
    planned: dict[str, str],
    settings: Settings | None,
    *,
    timings: GoldenCaptureTimings | None = None,
) -> GoldenCaptureHostSession | GoldenCaptureResult:
    """Return a reusable host session or a bootstrap failure result."""
    key = _session_key(project_dir, feature_name)
    cached = _WARM_SESSIONS.get(key)
    if cached is not None:
        return cached

    flutter = resolve_flutter_executable(sdk_root=settings.flutter_sdk if settings else None)
    if flutter is None:
        return GoldenCaptureResult(reason="no Flutter SDK (PATH or FIGMA_FLUTTER_SDK)")

    capture_dir = warm_capture_sandbox_dir(project_dir)
    bootstrap_failure = _ensure_sandbox_bootstrapped(
        capture_dir,
        flutter=flutter,
        timings=timings,
    )
    if bootstrap_failure is not None:
        return bootstrap_failure

    test_rel, fast_capture = _resolve_host_capture_test(planned, feature_name, settings)
    session = GoldenCaptureHostSession(
        capture_dir=capture_dir,
        feature_name=feature_name,
        golden_test_rel=test_rel,
        flutter=flutter,
        settings=settings,
        in_project=False,
        fast_capture=fast_capture,
        _tmp_handle=None,
    )
    _WARM_SESSIONS[key] = session
    logger.info(
        "Warm capture session for {} (sandbox {}; incremental flutter test after first compile)",
        feature_name,
        capture_dir.as_posix(),
    )
    return session


def capture_planned_in_warm_sandbox(
    planned: dict[str, str],
    *,
    feature_name: str,
    project_dir: Path,
    layout_tree: CleanDesignTreeNode | None,
    settings: Settings | None,
    timings: GoldenCaptureTimings | None = None,
) -> GoldenCaptureResult:
    """Capture a screen PNG in the persistent warm sandbox (not the full app tree)."""
    session_or_error = get_or_create_warm_session(
        project_dir,
        feature_name,
        planned,
        settings,
        timings=timings,
    )
    if isinstance(session_or_error, GoldenCaptureResult):
        return session_or_error

    return capture_planned_flutter_golden_png(
        planned,
        feature_name=feature_name,
        project_dir=project_dir,
        settings=settings,
        layout_tree=layout_tree,
        host_session=session_or_error,
        capture_in_project=False,
        timings=timings,
    )
