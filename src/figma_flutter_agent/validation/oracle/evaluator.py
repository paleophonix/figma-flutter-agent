"""Per-screen corpus oracle evaluation."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.fixtures.capture_context import resolve_fixture_project_dir
from figma_flutter_agent.fixtures.geometry_check import check_fixture_geometry
from figma_flutter_agent.fixtures.golden_compare import compare_fixture_golden
from figma_flutter_agent.fixtures.screens_manifest import ScreenFixtureEntry
from figma_flutter_agent.validation.oracle.models import ScreenOracleMetrics, ScreenOracleResult


def _strict_geometry_enabled(entry: ScreenFixtureEntry) -> bool:
    return "strict_geometry" in entry.oracle_modes


def _strict_pixel_enabled(entry: ScreenFixtureEntry) -> bool:
    return "strict_pixel" in entry.oracle_modes


def evaluate_screen_oracle(
    entry: ScreenFixtureEntry,
    *,
    settings: Settings | None = None,
    golden_runtime: str | None = None,
    project_dir: Path | None = None,
) -> ScreenOracleResult:
    """Evaluate oracle gates for one manifest screen.

    Args:
        entry: Screen fixture manifest entry.
        settings: Agent settings.
        golden_runtime: Optional golden capture runtime override.
        project_dir: Optional warm Flutter project directory.

    Returns:
        Per-screen oracle result with metrics and pass flags.
    """
    resolved = settings or Settings()
    warm_project = (
        project_dir
        if project_dir is not None
        else resolve_fixture_project_dir(
            resolved,
        )
    )
    failures: list[str] = []
    metrics = ScreenOracleMetrics()
    skipped = False
    skip_reason: str | None = None

    pixel_ok = True
    geometry_ok = True

    if entry.golden_id is not None and _strict_pixel_enabled(entry):
        pixel = compare_fixture_golden(
            entry,
            settings=resolved,
            golden_runtime=golden_runtime,
            project_dir=warm_project,
        )
        if pixel.skipped:
            skipped = True
            skip_reason = pixel.reason
            pixel_ok = False
        else:
            metrics = ScreenOracleMetrics(
                non_text_pixel_diff=pixel.non_text_pixel_diff,
                text_region_pixel_diff=pixel.text_region_pixel_diff,
                text_bounds_delta=pixel.text_bounds_delta,
            )
            if not pixel.ok:
                pixel_ok = False
                failures.append(pixel.reason or "non-text pixel gate failed")

    if not skipped and _strict_geometry_enabled(entry):
        geometry = check_fixture_geometry(
            entry,
            settings=resolved,
            min_iou=entry.thresholds.geometry_iou_min,
            golden_runtime=golden_runtime,
            project_dir=warm_project,
        )
        if geometry.skipped:
            skipped = True
            skip_reason = geometry.reason
            geometry_ok = False
        else:
            metrics = ScreenOracleMetrics(
                non_text_pixel_diff=metrics.non_text_pixel_diff,
                text_region_pixel_diff=metrics.text_region_pixel_diff,
                text_bounds_delta=metrics.text_bounds_delta,
                geometry_iou=geometry.min_iou_observed,
            )
            if not geometry.ok:
                geometry_ok = False
                failures.append(geometry.reason or "geometry gate failed")

    advisory_pass = True
    if metrics.text_region_pixel_diff is not None:
        advisory_pass = metrics.text_region_pixel_diff <= entry.thresholds.text_region_pixel_max

    is_blocking_tier = entry.corpus_tier == "strict_pixel_blocking"
    if skipped and is_blocking_tier:
        blocking_pass = False
    elif is_blocking_tier:
        blocking_pass = pixel_ok and geometry_ok and not failures
    else:
        blocking_pass = True

    return ScreenOracleResult(
        screen_id=entry.id,
        corpus_tier=entry.corpus_tier,
        skipped=skipped,
        skip_reason=skip_reason,
        blocking_pass=blocking_pass,
        advisory_pass=advisory_pass,
        metrics=metrics,
        failures=tuple(failures),
    )
