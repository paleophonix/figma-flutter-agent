"""Corpus oracle gate runner."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.fixtures.capture_context import resolve_fixture_project_dir
from figma_flutter_agent.fixtures.screens_manifest import (
    ScreenFixtureEntry,
    load_screens_manifest,
)
from figma_flutter_agent.generator.ir.fidelity.manifest import load_fidelity_manifest
from figma_flutter_agent.schemas.ir import FidelityTier, WidgetIrKind
from figma_flutter_agent.validation.golden_capture import FixtureCaptureBatch
from figma_flutter_agent.validation.oracle.evaluator import evaluate_screen_oracle
from figma_flutter_agent.validation.oracle.models import (
    CorpusGateReport,
    PromotionCandidate,
    ScreenOracleResult,
)
from figma_flutter_agent.validation.oracle.promotion_evidence import (
    classified_semantic_kinds_for_entry,
)


def _structural_metrics_pass(result: ScreenOracleResult, entry: ScreenFixtureEntry) -> bool:
    metrics = result.metrics
    if (
        metrics.non_text_pixel_diff is not None
        and metrics.non_text_pixel_diff > entry.thresholds.non_text_pixel_max
    ):
        return False
    if (
        metrics.geometry_iou is not None
        and metrics.geometry_iou < entry.thresholds.geometry_iou_min
    ):
        return False
    if (
        metrics.text_bounds_delta is not None
        and metrics.text_bounds_delta > entry.thresholds.text_bounds_delta_max
    ):
        return False
    return not result.failures


def _collect_promotion_candidates(
    results: tuple[ScreenOracleResult, ...],
    entries_by_id: dict[str, ScreenFixtureEntry],
    *,
    kinds_by_screen: dict[str, frozenset[WidgetIrKind]],
) -> tuple[PromotionCandidate, ...]:
    manifest = load_fidelity_manifest()
    candidates: list[PromotionCandidate] = []
    for manifest_entry in manifest.entries:
        if manifest_entry.default_tier != FidelityTier.NATIVE_UNVERIFIED:
            continue
        for result in results:
            if result.skipped:
                continue
            screen = entries_by_id.get(result.screen_id)
            if screen is None or screen.golden_id is None:
                continue
            if manifest_entry.kind not in kinds_by_screen.get(screen.id, frozenset()):
                continue
            if screen.golden_id in manifest_entry.fixture_ids:
                continue
            if not _structural_metrics_pass(result, screen):
                continue
            metrics = {
                "non_text_pixel_diff": result.metrics.non_text_pixel_diff,
                "text_region_pixel_diff": result.metrics.text_region_pixel_diff,
                "geometry_iou": result.metrics.geometry_iou,
            }
            candidates.append(
                PromotionCandidate(
                    fixture_id=screen.golden_id,
                    screen_id=screen.id,
                    kind=manifest_entry.kind.value,
                    current_tier=manifest_entry.default_tier.value,
                    recommend=True,
                    metrics=metrics,
                ),
            )
    return tuple(candidates)


def run_corpus_oracle(
    *,
    screen_ids: list[str] | None = None,
    settings: Settings | None = None,
    golden_runtime: str | None = None,
    project_dir: Path | None = None,
    include_advisory: bool = True,
) -> CorpusGateReport:
    """Run corpus oracle evaluation for manifest screens.

    Args:
        screen_ids: Optional subset of screen ids; default all manifest screens.
        settings: Agent settings.
        golden_runtime: Optional golden capture runtime override.
        project_dir: Optional warm Flutter project directory.
        include_advisory: When False, only evaluate strict_pixel_blocking screens.

    Returns:
        Aggregate gate report with per-screen results.
    """
    resolved = settings or Settings()
    manifest = load_screens_manifest()
    entries = manifest.screens
    if screen_ids is not None:
        wanted = frozenset(screen_ids)
        entries = [entry for entry in entries if entry.id in wanted]
    if not include_advisory:
        entries = [entry for entry in entries if entry.corpus_tier == "strict_pixel_blocking"]

    warm_project = (
        project_dir
        if project_dir is not None
        else resolve_fixture_project_dir(
            resolved,
        )
    )
    batch = FixtureCaptureBatch(settings=resolved, project_dir=warm_project)
    if golden_runtime is not None:
        batch.golden_runtime = batch.resolved_runtime(golden_runtime)
    results: list[ScreenOracleResult] = [
        evaluate_screen_oracle(
            entry,
            settings=resolved,
            golden_runtime=golden_runtime,
            project_dir=warm_project,
            capture_batch=batch,
        )
        for entry in entries
    ]
    entries_by_id = {entry.id: entry for entry in entries}
    result_tuple = tuple(results)

    blocking = [item for item in results if item.corpus_tier == "strict_pixel_blocking"]
    blocking_passed = all(item.blocking_pass for item in blocking) if blocking else True
    advisory_only_failures = sum(
        1
        for item in results
        if item.corpus_tier != "strict_pixel_blocking" and not item.advisory_pass
    )
    kinds_by_screen = {
        entry.id: classified_semantic_kinds_for_entry(entry) for entry in entries
    }
    promotion_candidates = _collect_promotion_candidates(
        result_tuple,
        entries_by_id,
        kinds_by_screen=kinds_by_screen,
    )
    full_corpus_passed = blocking_passed and advisory_only_failures == 0

    return CorpusGateReport(
        blocking_passed=blocking_passed,
        full_corpus_passed=full_corpus_passed,
        advisory_only_failures=advisory_only_failures,
        results=result_tuple,
        promotion_candidates=promotion_candidates,
    )
