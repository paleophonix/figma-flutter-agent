"""Unified warm capture runtime for fixture golden scripts and corpus oracle."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings, agent_repo_root
from figma_flutter_agent.fixtures.capture_context import resolve_fixture_project_dir
from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.fixtures.screens_manifest import ScreenFixtureEntry, load_layout_tree
from figma_flutter_agent.generator.planned.reconcile import reconcile_planned_dart_files
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.golden_capture.capture import capture_planned_flutter_golden_png
from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult
from figma_flutter_agent.validation.golden_runtime import (
    GoldenCaptureMode,
    GoldenRuntimeSelection,
    ResolvedGoldenRuntime,
    resolve_golden_runtime,
)

_PERF_DIR = agent_repo_root() / "logs" / "perf"


@dataclass
class GoldenCaptureTimings:
    """Phase timings for one golden capture attempt (E8.1 schema)."""

    feature: str = ""
    mode: str = "host"
    workspace: str = "temp"
    fast_capture: bool = False
    timings_sec: dict[str, float] = field(default_factory=dict)

    def add(self, phase: str, seconds: float) -> None:
        """Accumulate elapsed seconds for a named capture phase."""
        self.timings_sec[phase] = self.timings_sec.get(phase, 0.0) + seconds

    def to_json(self) -> dict[str, Any]:
        """Serialize to the E8.1 perf JSON schema."""
        return {
            "feature": self.feature,
            "mode": self.mode,
            "fastCapture": self.fast_capture,
            "workspace": self.workspace,
            "timingsSec": dict(sorted(self.timings_sec.items())),
        }


def resolve_local_capture_mode(
    *,
    settings: Settings | None = None,
    golden_runtime: GoldenCaptureMode | str | None = None,
    prefer_host_for_fixtures: bool = True,
) -> GoldenRuntimeSelection:
    """Resolve golden runtime for local fixture/oracle callers (E8.6 lite).

    When ``FIGMA_GOLDEN_RUNTIME`` is unset and YAML ``golden_capture`` is ``auto``,
    fixture workflows prefer ``host`` so warm sandbox reuse is available locally.
    Explicit env/YAML ``docker`` / ``host`` and CI overrides are unchanged.

    Args:
        settings: Agent settings.
        golden_runtime: Optional caller override.
        prefer_host_for_fixtures: When False, delegate to ``resolve_golden_runtime``.

    Returns:
        Resolved host or docker runtime selection.
    """
    if golden_runtime is not None:
        return resolve_golden_runtime(golden_runtime, settings=settings)  # type: ignore[arg-type]

    env_raw = os.environ.get("FIGMA_GOLDEN_RUNTIME", "").strip().lower()
    if env_raw:
        return resolve_golden_runtime(settings=settings)

    configured = settings.agent.runtime.golden_capture if settings is not None else "auto"
    if prefer_host_for_fixtures and configured == "auto":
        logger.info(
            "resolved runtime=host reason=fixture_local_prefer_host (FIGMA_GOLDEN_RUNTIME unset, golden_capture=auto)"
        )
        return GoldenRuntimeSelection(runtime="host", configured="auto")

    return resolve_golden_runtime(settings=settings)


@dataclass
class FixtureCaptureBatch:
    """Reusable warm capture context for multi-screen fixture runs."""

    settings: Settings
    project_dir: Path | None = None
    golden_runtime: ResolvedGoldenRuntime | None = None
    timings_dir: Path | None = None
    write_timings: bool = True

    def __post_init__(self) -> None:
        if self.project_dir is None:
            self.project_dir = resolve_fixture_project_dir(self.settings)
        env_timings = os.environ.get("FIGMA_GOLDEN_CAPTURE_TIMINGS", "").strip() in (
            "1",
            "true",
            "yes",
        )
        if env_timings:
            self.write_timings = True
        if self.timings_dir is None:
            self.timings_dir = _PERF_DIR

    def resolved_runtime(self, override: GoldenCaptureMode | str | None = None) -> ResolvedGoldenRuntime:
        """Return cached or freshly resolved runtime for this batch."""
        if override is not None:
            return resolve_local_capture_mode(
                settings=self.settings,
                golden_runtime=override,
            ).runtime
        if self.golden_runtime is not None:
            return self.golden_runtime
        selection = resolve_local_capture_mode(settings=self.settings)
        self.golden_runtime = selection.runtime
        return selection.runtime

    def capture_planned(
        self,
        planned: Mapping[str, str],
        *,
        feature_name: str,
        layout_tree: CleanDesignTreeNode | None = None,
        golden_runtime: GoldenCaptureMode | str | None = None,
    ) -> GoldenCaptureResult:
        """Capture one screen using warm sandbox when host + project_dir are available."""
        result = capture_planned_for_fixture(
            self,
            dict(planned),
            feature_name=feature_name,
            layout_tree=layout_tree,
            golden_runtime=golden_runtime,
        )
        if self.write_timings and result.timings is not None:
            self._persist_timings(result.timings)
        return result

    def capture_fixture_entry(
        self,
        entry: ScreenFixtureEntry,
        *,
        golden_runtime: GoldenCaptureMode | str | None = None,
    ) -> GoldenCaptureResult:
        """Build planned files and capture one manifest screen."""
        layout_tree = load_layout_tree(entry)
        planned = reconcile_planned_dart_files(build_fixture_planned_files(entry))
        return self.capture_planned(
            planned,
            feature_name=entry.feature,
            layout_tree=layout_tree,
            golden_runtime=golden_runtime,
        )

    def _persist_timings(self, timings: GoldenCaptureTimings) -> None:
        if self.timings_dir is None or not timings.feature:
            return
        self.timings_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.timings_dir / f"golden_capture_{timings.feature}.json"
        out_path.write_text(
            json.dumps(timings.to_json(), indent=2) + "\n",
            encoding="utf-8",
        )
        logger.debug("Wrote golden capture timings to {}", out_path.as_posix())


def capture_planned_for_fixture(
    batch: FixtureCaptureBatch | None,
    planned: dict[str, str],
    *,
    feature_name: str,
    layout_tree: CleanDesignTreeNode | None = None,
    settings: Settings | None = None,
    golden_runtime: GoldenCaptureMode | str | None = None,
    project_dir: Path | None = None,
    flutter_sdk: str | None = None,
) -> GoldenCaptureResult:
    """Route capture through warm sandbox (host + project) or legacy cold path.

    Args:
        batch: Optional batch context for runtime resolution and timings.
        planned: Planned Dart files map.
        feature_name: Screen feature slug.
        layout_tree: Optional layout tree for asset sync.
        settings: Settings when ``batch`` is None.
        golden_runtime: Optional runtime override.
        project_dir: Optional project root override.
        flutter_sdk: Optional Flutter SDK root.

    Returns:
        Golden capture result with optional phase timings attached.
    """
    resolved_settings = batch.settings if batch is not None else (settings or Settings())
    warm_project = (
        batch.project_dir
        if batch is not None and batch.project_dir is not None
        else (
            project_dir
            if project_dir is not None
            else resolve_fixture_project_dir(resolved_settings)
        )
    )
    if batch is not None:
        runtime = batch.resolved_runtime(golden_runtime)
    elif golden_runtime is not None:
        runtime = resolve_local_capture_mode(
            settings=resolved_settings,
            golden_runtime=golden_runtime,
        ).runtime
    else:
        runtime = resolve_local_capture_mode(settings=resolved_settings).runtime

    timings = GoldenCaptureTimings(feature=feature_name, mode=runtime, fast_capture=True)
    if runtime == "host" and warm_project is not None and warm_project.is_dir():
        from figma_flutter_agent.dev.warm_capture import capture_planned_in_warm_sandbox

        timings.mode = "host_sandbox"
        timings.workspace = "sandbox"
        t0 = time.monotonic()
        result = capture_planned_in_warm_sandbox(
            planned,
            feature_name=feature_name,
            project_dir=warm_project,
            layout_tree=layout_tree,
            settings=resolved_settings,
            timings=timings,
        )
        timings.add("warmSandbox", time.monotonic() - t0)
    else:
        if runtime == "docker":
            timings.mode = "docker"
            timings.workspace = "docker"
        else:
            timings.mode = "host_cold"
            timings.workspace = "temp"
        t0 = time.monotonic()
        result = capture_planned_flutter_golden_png(
            planned,
            feature_name=feature_name,
            settings=resolved_settings,
            golden_runtime=runtime,
            flutter_sdk=flutter_sdk,
            layout_tree=layout_tree,
            project_dir=warm_project,
            timings=timings,
        )
        timings.add("totalCapture", time.monotonic() - t0)

    if result.timings is None:
        return GoldenCaptureResult(
            png=result.png,
            reason=result.reason,
            figma_key_rects=result.figma_key_rects,
            host_session=result.host_session,
            renderflex_overflows=result.renderflex_overflows,
            timings=timings,
        )
    return result


def monotonic_phase(timings: GoldenCaptureTimings | None, phase: str):
    """Context manager that records monotonic elapsed time into ``timings``."""

    class _Phase:
        def __init__(self) -> None:
            self._start = 0.0

        def __enter__(self) -> None:
            if timings is not None:
                self._start = time.monotonic()

        def __exit__(self, *_args: object) -> None:
            if timings is not None:
                timings.add(phase, time.monotonic() - self._start)

    return _Phase()
