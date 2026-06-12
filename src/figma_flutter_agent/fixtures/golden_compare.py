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
from figma_flutter_agent.validation.golden_runtime import (
    ResolvedGoldenRuntime,
    resolve_golden_runtime,
)
from figma_flutter_agent.validation.pixel.split_compare import compare_png_bytes_split


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

    runtime: ResolvedGoldenRuntime
    if golden_runtime is None:
        runtime = resolve_golden_runtime(settings=resolved_settings).runtime
    else:
        runtime = golden_runtime  # type: ignore[assignment]
    sdk = flutter_sdk if flutter_sdk is not None else resolved_settings.flutter_sdk or None
    warm_project = (
        project_dir
        if project_dir is not None
        else resolve_fixture_project_dir(
            resolved_settings,
        )
    )

    from figma_flutter_agent.validation.golden_capture import capture_planned_flutter_golden_png

    layout_tree = load_layout_tree(entry)
    planned = reconcile_planned_dart_files(build_fixture_planned_files(entry))
    capture = capture_planned_flutter_golden_png(
        planned,
        feature_name=entry.feature,
        settings=resolved_settings,
        golden_runtime=runtime,
        flutter_sdk=sdk,
        layout_tree=layout_tree,
        project_dir=warm_project,
    )
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

    split = compare_png_bytes_split(
        baseline,
        capture.png,
        clean_tree=layout_tree,
        non_text_pixel_max=threshold,
        text_region_pixel_max=entry.thresholds.text_region_pixel_max,
        text_bounds_delta_max=entry.thresholds.text_bounds_delta_max,
        resize_reference=False,
    )
    if split.passed_blocking:
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


def compare_all_fixture_goldens(
    *,
    screen_ids: list[str] | None = None,
    settings: Settings | None = None,
    baseline_dir: Path | None = None,
    pixel_threshold: float | None = None,
    golden_runtime: str | None = None,
    project_dir: Path | None = None,
) -> list[FixtureGoldenCompareResult]:
    """Compare every manifest screen to its committed baseline."""
    manifest = load_screens_manifest()
    entries = manifest.screens
    if screen_ids is not None:
        wanted = frozenset(screen_ids)
        entries = [entry for entry in entries if entry.id in wanted]
    resolved_settings = settings or Settings()
    sdk = resolved_settings.flutter_sdk or None
    warm_project = (
        project_dir
        if project_dir is not None
        else resolve_fixture_project_dir(
            resolved_settings,
        )
    )
    return [
        compare_fixture_golden(
            entry,
            settings=resolved_settings,
            baseline_dir=baseline_dir,
            pixel_threshold=pixel_threshold,
            golden_runtime=golden_runtime,
            flutter_sdk=sdk,
            project_dir=warm_project,
        )
        for entry in entries
        if entry.golden_id is not None
    ]
