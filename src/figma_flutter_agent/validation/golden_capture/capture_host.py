"""Host-runtime screen capture execution for golden capture."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from figma_flutter_agent.validation.golden_capture.warm_runtime import (
        GoldenCaptureTimings,
    )

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.render_log import record_render_png
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.tools.process_run import (
    FLUTTER_TEST_TIMEOUT_SEC,
    run_subprocess,
)
from figma_flutter_agent.validation.golden_capture.logs import (
    _clip_reason,
    _log_process_output,
)
from figma_flutter_agent.validation.golden_capture.paths import (
    capture_test_relative_path,
    collect_planned_asset_paths,
    golden_png_relative_path,
    golden_test_relative_path,
)
from figma_flutter_agent.validation.golden_capture.project import (
    _materialize_capture_workspace,
    _run_flutter_pub_get,
    _safe_temp_cleanup,
    _write_planned_for_golden_capture,
)
from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult

CAPTURE_OUT_ENV = "FIGMA_FLUTTER_CAPTURE_OUT"
CAPTURE_KEYS_OUT_ENV = "FIGMA_FLUTTER_CAPTURE_KEYS_OUT"


@dataclass
class GoldenCaptureHostSession:
    """Reusable capture root (Flutter project dir or temp sandbox)."""

    capture_dir: Path
    feature_name: str
    golden_test_rel: str
    flutter: str
    settings: Settings | None
    in_project: bool = False
    fast_capture: bool = False
    _tmp_handle: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self._tmp_handle is not None:
            _safe_temp_cleanup(self._tmp_handle)

    def refresh_and_capture(
        self,
        planned: Mapping[str, str],
        *,
        project_dir: Path | None,
        layout_tree: CleanDesignTreeNode | None,
        timings: GoldenCaptureTimings | None = None,
    ) -> GoldenCaptureResult:
        """Rewrite planned Dart and re-run golden test in the existing capture root."""
        import time

        from figma_flutter_agent.validation.golden_capture.capture_host_run import (
            _run_golden_test_in_workspace,
        )

        if self.in_project:
            write_started = time.monotonic()
            _write_planned_for_golden_capture(
                self.capture_dir,
                planned,
                layout_tree=layout_tree,
            )
            if timings is not None:
                timings.add("writePlanned", time.monotonic() - write_started)
            return _run_golden_test_in_workspace(
                self.capture_dir,
                feature_name=self.feature_name,
                golden_test_rel=self.golden_test_rel,
                flutter=self.flutter,
                settings=self.settings,
                skip_build_clean=True,
                in_project=True,
                fast_capture=self.fast_capture,
                timings=timings,
            )
        materialize_started = time.monotonic()
        capture_planned = _materialize_capture_workspace(
            self.capture_dir,
            planned,
            enable_backup=False,
            layout_tree=layout_tree,
            project_dir=project_dir,
        )
        if timings is not None:
            timings.add("writePlanned", time.monotonic() - materialize_started)
            timings.add("syncAssets", 0.0)
        pub_get_failure = _run_flutter_pub_get(self.capture_dir, self.flutter, timings=timings)
        if pub_get_failure is not None:
            return pub_get_failure
        return _run_golden_test_in_workspace(
            self.capture_dir,
            feature_name=self.feature_name,
            golden_test_rel=self.golden_test_rel,
            flutter=self.flutter,
            settings=self.settings,
            skip_build_clean=True,
            asset_paths_hint=len(collect_planned_asset_paths(capture_planned, layout_tree)),
            fast_capture=self.fast_capture,
            timings=timings,
        )


def _visual_refine_fast_capture(settings: Settings | None) -> bool:
    if settings is None:
        return True
    return not settings.agent.generation.llm_visual_refine_capture_golden


def _capture_collects_figma_keys(settings: Settings | None) -> bool:
    if settings is None:
        return False
    generation = settings.agent.generation
    return generation.runtime_geometry_gate or generation.runtime_geometry_capture_if_missing


def _resolve_host_capture_test(
    planned: Mapping[str, str],
    feature_name: str,
    settings: Settings | None,
) -> tuple[str, bool]:
    """Return ``(test_rel, fast_capture)`` for host visual-refine capture."""
    if _visual_refine_fast_capture(settings):
        capture_rel = capture_test_relative_path(feature_name)
        if capture_rel in planned:
            return capture_rel, True
    golden_rel = golden_test_relative_path(feature_name)
    return golden_rel, False


def _capture_png_out_path(capture_dir: Path, feature_name: str) -> Path:
    return capture_dir / ".figma_flutter_capture" / f"{feature_name}_screen.png"


def _capture_keys_out_path(capture_dir: Path, feature_name: str) -> Path:
    return capture_dir / ".figma_flutter_capture" / f"{feature_name}_figma_keys.json"


def _resolve_flutter_test_timeout(settings: Settings | None) -> float:
    if settings is not None:
        return settings.agent.generation.golden_capture_timeout_sec
    return FLUTTER_TEST_TIMEOUT_SEC


def _try_salvage_golden_png(
    capture_dir: Path,
    feature_name: str,
    *,
    failure_reason: str,
) -> GoldenCaptureResult | None:
    """Use an on-disk golden PNG when ``flutter test`` died after writing it."""
    golden_out = capture_dir / golden_png_relative_path(feature_name)
    if not golden_out.is_file():
        return None
    png = golden_out.read_bytes()
    if len(png) < 64:
        return None
    logger.warning(
        "Golden capture recovered PNG from {} after failure ({})",
        golden_out,
        failure_reason,
    )
    record_render_png(
        "flutter_render",
        png,
        extra={
            "featureName": feature_name,
            "runtime": "host",
            "salvaged": True,
            "failureReason": failure_reason,
        },
    )
    figma_key_rects = _read_figma_key_rects(capture_dir, feature_name)
    return GoldenCaptureResult(png=png, figma_key_rects=figma_key_rects)


def _read_figma_key_rects(capture_dir: Path, feature_name: str) -> dict[str, Any] | None:
    """Read figma key rects from the golden output directory."""
    from figma_flutter_agent.validation.golden_capture.paths import _read_figma_key_rects as _read

    return _read(capture_dir, feature_name)


def _flutter_test_render_args(
    capture_dir: Path,
    test_rel: str,
    settings: Settings | None,
) -> list[str]:
    """Artboard preview ``--dart-define`` flags for capture renders (always 1:1)."""
    _ = settings
    test_path = capture_dir / test_rel
    if not test_path.is_file():
        return []
    from figma_flutter_agent.generator.capture_screen_test import infer_test_surface_size
    from figma_flutter_agent.generator.render_surface import capture_render_dart_defines

    source = test_path.read_text(encoding="utf-8")
    width, height = infer_test_surface_size(source)
    return capture_render_dart_defines(surface_width=width, surface_height=height)


def _run_screen_capture_flutter_test(
    flutter: str,
    capture_dir: Path,
    capture_test_rel: str,
    *,
    png_out: Path,
    keys_out: Path | None,
    timeout_sec: float,
    stream_output: bool = False,
    extra_test_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str] | GoldenCaptureResult:
    """Run a capture-only widget test (PNG to env path, no golden compare)."""
    png_out.parent.mkdir(parents=True, exist_ok=True)
    env: dict[str, str] = {CAPTURE_OUT_ENV: str(png_out.resolve())}
    if keys_out is not None:
        keys_out.parent.mkdir(parents=True, exist_ok=True)
        env[CAPTURE_KEYS_OUT_ENV] = str(keys_out.resolve())
    if stream_output:
        logger.info(
            "Flutter screen capture starting (first compile in a warm project is often "
            "3–8 min on Windows; limit {:.0f}s). Compiler output streams below.",
            timeout_sec,
        )
    else:
        logger.info(
            "Flutter screen capture starting (warm project often a few seconds; limit {:.0f}s)",
            timeout_sec,
        )
    try:
        test_cmd = [
            flutter,
            "test",
            capture_test_rel,
            "--no-pub",
            "--reporter",
            "silent",
            "--fail-fast",
            *(extra_test_args or ()),
        ]
        return run_subprocess(
            test_cmd,
            cwd=capture_dir,
            label="flutter test capture",
            timeout_sec=timeout_sec,
            stream_output=stream_output,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        _log_process_output(
            subprocess.CompletedProcess([], 1, exc.stdout, exc.stderr),
            level="warning",
        )
        return GoldenCaptureResult(
            reason=_clip_reason(
                f"flutter screen capture timed out after {timeout_sec:.0f}s "
                "(often Dart compile for `flutter test` on a large layout — "
                "raise generation.golden_capture_timeout_sec; "
                "or check unbounded Stack/Flex / missing assets if compile finished quickly)"
            ),
        )


def _run_golden_flutter_test(
    flutter: str,
    capture_dir: Path,
    golden_test_rel: str,
    *,
    timeout_sec: float,
    extra_test_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str] | GoldenCaptureResult:
    """Run a single golden widget test with bounded timeout."""
    logger.info(
        "Flutter golden test starting (first compile in this temp workspace is often 3–8 min; "
        "hard limit {:.0f}s). Compiler output streams below.",
        timeout_sec,
    )
    try:
        test_cmd = [
            flutter,
            "test",
            golden_test_rel,
            "--update-goldens",
            "--no-pub",
            "--reporter",
            "expanded",
            "--timeout",
            "2m",
            "--fail-fast",
            *(extra_test_args or ()),
        ]
        return run_subprocess(
            test_cmd,
            cwd=capture_dir,
            label="flutter test --update-goldens",
            timeout_sec=timeout_sec,
            stream_output=True,
        )
    except subprocess.TimeoutExpired as exc:
        _log_process_output(
            subprocess.CompletedProcess([], 1, exc.stdout, exc.stderr),
            level="warning",
        )
        return GoldenCaptureResult(
            reason=_clip_reason(
                f"flutter test timed out after {timeout_sec:.0f}s "
                "(layout may not settle — check unbounded Stack/Flex or missing assets)"
            ),
        )
