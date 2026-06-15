"""Compare fresh golden captures against committed fixture baselines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.fixtures.capture_context import resolve_fixture_project_dir
from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.fixtures.screens_manifest import (
    ScreenFixtureEntry,
    fixtures_root,
    load_layout_tree,
    load_screens_manifest,
)
from figma_flutter_agent.generator.planned.reconcile import reconcile_planned_dart_files
from figma_flutter_agent.validation.golden_capture import (
    FixtureCaptureBatch,
    GoldenCaptureResult,
    capture_planned_for_fixture,
)
from figma_flutter_agent.validation.pixel.coordinates import parse_flutter_mapper_payload
from figma_flutter_agent.validation.pixel.perfect_gate import (
    compare_png_bytes_pixel_perfect,
    passed_pixel_perfect_gate,
)
from figma_flutter_agent.validation.pixel.split_compare import compare_png_bytes_split


def _use_pixel_perfect_gate(settings: Settings | None) -> bool:
    if settings is None:
        return False
    from figma_flutter_agent.config.fidelity_policy import RenderProfile, resolve_render_profile

    generation = settings.agent.generation
    return bool(
        generation.pixel_fidelity
        or resolve_render_profile(settings.agent) == RenderProfile.VISUAL_PIXEL,
    )


@dataclass(frozen=True)
class FixtureGoldenCompareResult:
    """Outcome of comparing one fixture screen to its baseline PNG."""

    screen_id: str
    ok: bool
    skipped: bool = False
    reason: str | None = None
    changed_ratio: float | None = None
    non_text_pixel_diff: float | None = None
    text_region_pixel_diff: float | None = None
    text_bounds_delta: float | None = None


def _baseline_path(entry: ScreenFixtureEntry, *, baseline_dir: Path) -> Path:
    if entry.golden_id is None:
        raise FigmaFlutterError(f"Screen fixture {entry.id} has no golden_id")
    return baseline_dir / f"{entry.golden_id}.png"


def _compare_capture_to_baseline(
    entry: ScreenFixtureEntry,
    capture: GoldenCaptureResult,
    *,
    baseline_path: Path,
    threshold: float,
    layout_tree,
    use_split_compare: bool,
    settings: Settings | None = None,
) -> FixtureGoldenCompareResult:
    if not capture.ok or capture.png is None:
        return FixtureGoldenCompareResult(
            screen_id=entry.id,
            ok=False,
            skipped=True,
            reason=capture.reason or "capture failed",
        )

    baseline = baseline_path.read_bytes()
    if not use_split_compare:
        from figma_flutter_agent.validation.compare import compare_png_bytes
        from figma_flutter_agent.validation.pixel.models import PixelDiffResult

        legacy_diff = compare_png_bytes(baseline, capture.png, threshold=threshold)
        if not isinstance(legacy_diff, PixelDiffResult):
            msg = "legacy compare without clean_tree must return PixelDiffResult"
            raise FigmaFlutterError(msg)
        changed = legacy_diff.changed_ratio
        return FixtureGoldenCompareResult(
            screen_id=entry.id,
            ok=legacy_diff.passed,
            changed_ratio=changed,
            non_text_pixel_diff=changed,
            reason=None if legacy_diff.passed else f"pixel diff {changed:.2%} > {threshold:.2%}",
        )

    flutter_mapper = parse_flutter_mapper_payload(capture.figma_key_rects)
    if _use_pixel_perfect_gate(settings):
        split = compare_png_bytes_pixel_perfect(
            baseline,
            capture.png,
            clean_tree=layout_tree,
        )
        ok = passed_pixel_perfect_gate(split, blocking_text=True)
    else:
        split = compare_png_bytes_split(
            baseline,
            capture.png,
            clean_tree=layout_tree,
            flutter_mapper=flutter_mapper,
            non_text_pixel_max=threshold,
            text_region_pixel_max=entry.thresholds.text_region_pixel_max,
            text_bounds_delta_max=entry.thresholds.text_bounds_delta_max,
            resize_reference=False,
        )
        ok = split.passed_blocking
    if ok:
        return FixtureGoldenCompareResult(
            screen_id=entry.id,
            ok=True,
            changed_ratio=split.non_text_pixel_diff,
            non_text_pixel_diff=split.non_text_pixel_diff,
            text_region_pixel_diff=split.text_region_pixel_diff,
            text_bounds_delta=split.text_bounds_delta,
        )
    if not split.text_validation_passed:
        reason = (
            f"text bounds delta {split.text_bounds_delta:.1f} > {split.text_bounds_delta_max:.1f}"
        )
    else:
        reason = f"non-text pixel diff {split.non_text_pixel_diff:.2%} > {threshold:.2%}"
    return FixtureGoldenCompareResult(
        screen_id=entry.id,
        ok=False,
        reason=reason,
        changed_ratio=split.non_text_pixel_diff,
        non_text_pixel_diff=split.non_text_pixel_diff,
        text_region_pixel_diff=split.text_region_pixel_diff,
        text_bounds_delta=split.text_bounds_delta,
    )


def compare_fixture_golden(
    entry: ScreenFixtureEntry,
    *,
    settings: Settings | None = None,
    baseline_dir: Path | None = None,
    pixel_threshold: float | None = None,
    golden_runtime: str | None = None,
    flutter_sdk: str | None = None,
    project_dir: Path | None = None,
    use_split_compare: bool = True,
    capture_batch: FixtureCaptureBatch | None = None,
    existing_capture: GoldenCaptureResult | None = None,
) -> FixtureGoldenCompareResult:
    """Capture a screen and compare to the committed docker baseline PNG."""
    resolved_settings = settings or Settings()
    threshold = (
        pixel_threshold if pixel_threshold is not None else entry.thresholds.non_text_pixel_max
    )
    baseline_root = baseline_dir or (fixtures_root() / "golden" / "png" / "docker")
    baseline_path = _baseline_path(entry, baseline_dir=baseline_root)
    if not baseline_path.is_file():
        return FixtureGoldenCompareResult(
            screen_id=entry.id,
            ok=False,
            skipped=True,
            reason=f"baseline missing: {baseline_path}",
        )

    layout_tree = load_layout_tree(entry)
    if existing_capture is not None:
        capture = existing_capture
    else:
        sdk = flutter_sdk if flutter_sdk is not None else resolved_settings.flutter_sdk or None
        warm_project = (
            project_dir
            if project_dir is not None
            else resolve_fixture_project_dir(
                resolved_settings,
            )
        )
        if capture_batch is not None:
            capture = capture_batch.capture_fixture_entry(
                entry,
                golden_runtime=golden_runtime,
            )
        else:
            planned = reconcile_planned_dart_files(build_fixture_planned_files(entry))
            capture = capture_planned_for_fixture(
                None,
                planned,
                feature_name=entry.feature,
                layout_tree=layout_tree,
                settings=resolved_settings,
                golden_runtime=golden_runtime,
                project_dir=warm_project,
                flutter_sdk=sdk,
            )

    return _compare_capture_to_baseline(
        entry,
        capture,
        baseline_path=baseline_path,
        threshold=threshold,
        layout_tree=layout_tree,
        use_split_compare=use_split_compare,
        settings=resolved_settings,
    )


def compare_all_fixture_goldens(
    *,
    screen_ids: list[str] | None = None,
    settings: Settings | None = None,
    baseline_dir: Path | None = None,
    pixel_threshold: float | None = None,
    golden_runtime: str | None = None,
    project_dir: Path | None = None,
    capture_batch: FixtureCaptureBatch | None = None,
) -> list[FixtureGoldenCompareResult]:
    """Compare every manifest screen to its committed baseline."""
    manifest = load_screens_manifest()
    entries = manifest.screens
    if screen_ids is not None:
        wanted = frozenset(screen_ids)
        entries = [entry for entry in entries if entry.id in wanted]
    resolved_settings = settings or Settings()
    batch = capture_batch or FixtureCaptureBatch(
        settings=resolved_settings,
        project_dir=project_dir,
    )
    if golden_runtime is not None:
        batch.golden_runtime = batch.resolved_runtime(golden_runtime)
    return [
        compare_fixture_golden(
            entry,
            settings=resolved_settings,
            baseline_dir=baseline_dir,
            pixel_threshold=pixel_threshold,
            golden_runtime=golden_runtime,
            project_dir=batch.project_dir,
            capture_batch=batch,
        )
        for entry in entries
        if entry.golden_id is not None
    ]
