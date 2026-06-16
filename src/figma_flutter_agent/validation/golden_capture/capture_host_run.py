"""Workspace test execution and host capture orchestration."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable
from figma_flutter_agent.render_log import expected_render_png_path, record_render_png
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.golden_capture.logs import (
    _clip_reason,
    _first_process_line,
    _log_process_output,
)
from figma_flutter_agent.validation.golden_capture.paths import (
    collect_planned_asset_paths,
    golden_png_relative_path,
)
from figma_flutter_agent.validation.golden_capture.project import (
    _ensure_flutter_test_build_dir_hygienic,
    _materialize_capture_workspace,
    _prepare_capture_workspace,
    _prepare_flutter_test_build_dir,
    _run_flutter_pub_get,
    _safe_temp_cleanup,
    _write_planned_for_golden_capture,
)
from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult

if TYPE_CHECKING:
    from figma_flutter_agent.validation.golden_capture.warm_runtime import (
        GoldenCaptureTimings,
    )

from .capture_host import (
    GoldenCaptureHostSession,
    _capture_collects_figma_keys,
    _capture_keys_out_path,
    _capture_png_out_path,
    _flutter_test_render_args,
    _read_figma_key_rects,
    _resolve_flutter_test_timeout,
    _resolve_host_capture_test,
    _run_golden_flutter_test,
    _run_screen_capture_flutter_test,
    _try_salvage_golden_png,
)


def _run_golden_test_in_workspace(
    capture_dir: Path,
    *,
    feature_name: str,
    golden_test_rel: str,
    flutter: str,
    settings: Settings | None,
    skip_build_clean: bool,
    asset_paths_hint: int = 0,
    in_project: bool = False,
    fast_capture: bool = False,
    timings: GoldenCaptureTimings | None = None,
) -> GoldenCaptureResult:
    if not _ensure_flutter_test_build_dir_hygienic(capture_dir):
        return GoldenCaptureResult(
            reason=_clip_reason(
                "flutter test build directory is not writable "
                f"({capture_dir / 'build'}); close other dart/flutter processes and retry"
            ),
        )
    if not skip_build_clean:
        t0 = time.monotonic()
        _prepare_flutter_test_build_dir(capture_dir)
        if timings is not None:
            timings.add("prepareWorkspace", time.monotonic() - t0)
        pub_get_failure = _run_flutter_pub_get(capture_dir, flutter, timings=timings)
        if pub_get_failure is not None:
            return pub_get_failure
    png_out = (
        _capture_png_out_path(capture_dir, feature_name)
        if fast_capture
        else capture_dir / golden_png_relative_path(feature_name)
    )
    keys_out = (
        _capture_keys_out_path(capture_dir, feature_name)
        if fast_capture and _capture_collects_figma_keys(settings)
        else None
    )
    render_dest = expected_render_png_path("flutter_render")
    if in_project:
        logger.info(
            "Rendering Flutter screen for {} in project {} ({}) {}{} → {}",
            feature_name,
            capture_dir,
            golden_test_rel,
            "capture " if fast_capture else "golden ",
            png_out,
            render_dest.resolve() if render_dest is not None else ".debug/renders",
        )
    elif render_dest is not None:
        logger.info(
            "Rendering Flutter screen for {} ({}); {}{} → combat log {}{}",
            feature_name,
            golden_test_rel,
            "capture " if fast_capture else "golden ",
            png_out,
            render_dest.resolve(),
            f" ({asset_paths_hint} assets synced)" if asset_paths_hint else "",
        )
    else:
        logger.info(
            "Rendering Flutter screen for {} ({}); output {}",
            feature_name,
            golden_test_rel,
            png_out,
        )
    test_timeout = _resolve_flutter_test_timeout(settings)
    render_args = _flutter_test_render_args(capture_dir, golden_test_rel, settings)
    test_started = time.monotonic()
    if fast_capture:
        test_outcome = _run_screen_capture_flutter_test(
            flutter,
            capture_dir,
            golden_test_rel,
            png_out=png_out,
            keys_out=keys_out,
            timeout_sec=test_timeout,
            stream_output=in_project or fast_capture,
            extra_test_args=render_args,
        )
    else:
        test_outcome = _run_golden_flutter_test(
            flutter,
            capture_dir,
            golden_test_rel,
            timeout_sec=test_timeout,
            extra_test_args=render_args,
        )
    if timings is not None:
        timings.add("flutterTest", time.monotonic() - test_started)
        timings.fast_capture = fast_capture
    if isinstance(test_outcome, GoldenCaptureResult):
        if fast_capture:
            return test_outcome
        salvaged = _try_salvage_golden_png(
            capture_dir,
            feature_name,
            failure_reason=test_outcome.reason or "flutter test failed",
        )
        if salvaged is not None:
            return salvaged
        return test_outcome
    result = test_outcome
    if result.returncode != 0:
        _log_process_output(result, level="warning")
        reason = _first_process_line(result)
        if fast_capture:
            return GoldenCaptureResult(reason=reason)
        salvaged = _try_salvage_golden_png(
            capture_dir,
            feature_name,
            failure_reason=reason,
        )
        if salvaged is not None:
            return salvaged
        return GoldenCaptureResult(reason=reason)
    if not png_out.is_file():
        logger.warning("Capture PNG was not written: {}", png_out)
        return GoldenCaptureResult(reason="screen capture PNG not written")
    read_started = time.monotonic()
    png = png_out.read_bytes()
    if fast_capture and keys_out is not None and keys_out.is_file():
        raw = keys_out.read_text(encoding="utf-8").strip()
        try:
            figma_key_rects = json.loads(raw) if raw else None
        except json.JSONDecodeError as exc:
            logger.warning("Capture: invalid {} ({})", keys_out.name, exc)
            figma_key_rects = None
    else:
        figma_key_rects = _read_figma_key_rects(capture_dir, feature_name)
    saved = record_render_png(
        "flutter_render",
        png,
        extra={"featureName": feature_name, "runtime": "host", "goldenPath": str(png_out)},
    )
    if saved is None:
        logger.warning(
            "Golden PNG captured at {} but not copied to .debug/renders/ "
            "(enable generation.llm_visual_refine)",
            png_out,
        )
    from figma_flutter_agent.validation.golden_capture.logs import collect_renderflex_overflows

    overflows = collect_renderflex_overflows(result.stdout, result.stderr)
    if timings is not None:
        timings.add("readPng", time.monotonic() - read_started)
    return GoldenCaptureResult(
        png=png,
        figma_key_rects=figma_key_rects,
        renderflex_overflows=overflows,
        timings=timings,
    )


def _capture_planned_flutter_golden_png_in_project(
    planned: dict[str, str],
    *,
    feature_name: str,
    project_dir: Path,
    layout_tree: CleanDesignTreeNode | None,
    flutter: str,
    settings: Settings | None,
    golden_test_rel: str,
    host_session: GoldenCaptureHostSession | None,
    fast_capture: bool = False,
    timings: GoldenCaptureTimings | None = None,
) -> GoldenCaptureResult:
    """Run golden capture in the user's Flutter project (no temp tree, no asset copy)."""
    if host_session is not None and host_session.in_project:
        result = host_session.refresh_and_capture(
            planned,
            project_dir=project_dir,
            layout_tree=layout_tree,
            timings=timings,
        )
        if result.ok:
            return GoldenCaptureResult(
                png=result.png,
                figma_key_rects=result.figma_key_rects,
                host_session=host_session,
                timings=result.timings or timings,
            )
        host_session.close()
        return result

    write_started = time.monotonic()
    _write_planned_for_golden_capture(
        project_dir,
        planned,
        layout_tree=layout_tree,
    )
    if timings is not None:
        timings.add("writePlanned", time.monotonic() - write_started)
    pub_get_failure = _run_flutter_pub_get(project_dir, flutter, timings=timings)
    if pub_get_failure is not None:
        return pub_get_failure
    result = _run_golden_test_in_workspace(
        project_dir,
        feature_name=feature_name,
        golden_test_rel=golden_test_rel,
        flutter=flutter,
        settings=settings,
        skip_build_clean=True,
        in_project=True,
        fast_capture=fast_capture,
        timings=timings,
    )
    if not result.ok:
        return result
    session = GoldenCaptureHostSession(
        capture_dir=project_dir,
        feature_name=feature_name,
        golden_test_rel=golden_test_rel,
        flutter=flutter,
        settings=settings,
        in_project=True,
        fast_capture=fast_capture,
        _tmp_handle=None,
    )
    return GoldenCaptureResult(
        png=result.png,
        figma_key_rects=result.figma_key_rects,
        host_session=session,
        timings=result.timings or timings,
    )


def capture_planned_flutter_golden_png_host(
    planned: dict[str, str],
    *,
    feature_name: str,
    flutter_sdk: str | Path | None = None,
    project_dir: Path | None = None,
    layout_tree: CleanDesignTreeNode | None = None,
    settings: Settings | None = None,
    host_session: GoldenCaptureHostSession | None = None,
    capture_in_project: bool = True,
    timings: GoldenCaptureTimings | None = None,
) -> GoldenCaptureResult:
    """Capture a Flutter screen PNG on the host (fast capture or golden test)."""
    from figma_flutter_agent.validation.golden_capture.project import _FLUTTER_SKELETON

    flutter = resolve_flutter_executable(sdk_root=flutter_sdk)
    if flutter is None:
        return GoldenCaptureResult(reason="no Flutter SDK (PATH or FIGMA_FLUTTER_SDK)")

    test_rel, fast_capture = _resolve_host_capture_test(planned, feature_name, settings)
    if timings is not None:
        timings.fast_capture = fast_capture
    if test_rel not in planned:
        return GoldenCaptureResult(reason=f"no {test_rel} in plan")

    if not _FLUTTER_SKELETON.is_dir():
        logger.debug("Flutter skeleton missing at {}", _FLUTTER_SKELETON)
        return GoldenCaptureResult(reason="flutter skeleton fixture missing")

    if project_dir is not None and project_dir.is_dir() and capture_in_project:
        return _capture_planned_flutter_golden_png_in_project(
            planned,
            feature_name=feature_name,
            project_dir=project_dir,
            layout_tree=layout_tree,
            flutter=flutter,
            settings=settings,
            golden_test_rel=test_rel,
            host_session=host_session,
            fast_capture=fast_capture,
            timings=timings,
        )

    if host_session is not None:
        result = host_session.refresh_and_capture(
            planned,
            project_dir=project_dir,
            layout_tree=layout_tree,
            timings=timings,
        )
        if result.ok:
            return GoldenCaptureResult(
                png=result.png,
                figma_key_rects=result.figma_key_rects,
                host_session=host_session,
                timings=result.timings or timings,
            )
        host_session.close()
        return result

    prep_started = time.monotonic()
    capture_dir, tmp_handle = _prepare_capture_workspace()
    if timings is not None:
        timings.workspace = "temp"
        timings.add("prepareWorkspace", time.monotonic() - prep_started)
    try:
        materialize_started = time.monotonic()
        capture_planned = _materialize_capture_workspace(
            capture_dir,
            planned,
            enable_backup=False,
            layout_tree=layout_tree,
            project_dir=project_dir,
        )
        if timings is not None:
            timings.add("writePlanned", time.monotonic() - materialize_started)
            timings.add(
                "syncAssets",
                0.0,
            )
        result = _run_golden_test_in_workspace(
            capture_dir,
            feature_name=feature_name,
            golden_test_rel=test_rel,
            flutter=flutter,
            settings=settings,
            skip_build_clean=False,
            asset_paths_hint=len(collect_planned_asset_paths(capture_planned, layout_tree)),
            fast_capture=fast_capture,
            timings=timings,
        )
        if not result.ok:
            return result
        session = GoldenCaptureHostSession(
            capture_dir=capture_dir,
            feature_name=feature_name,
            golden_test_rel=test_rel,
            flutter=flutter,
            settings=settings,
            in_project=False,
            fast_capture=fast_capture,
            _tmp_handle=tmp_handle,
        )
        return GoldenCaptureResult(
            png=result.png,
            figma_key_rects=result.figma_key_rects,
            host_session=session,
            timings=result.timings or timings,
        )
    except Exception:
        _safe_temp_cleanup(tmp_handle)
        raise
