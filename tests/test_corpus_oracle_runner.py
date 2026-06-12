"""Corpus oracle runner unit tests."""

from __future__ import annotations

from unittest.mock import patch

from figma_flutter_agent.fixtures.screens_manifest import OracleThresholds, ScreenFixtureEntry
from figma_flutter_agent.validation.oracle.models import ScreenOracleMetrics, ScreenOracleResult
from figma_flutter_agent.validation.oracle.runner import run_corpus_oracle


def _entry(screen_id: str, *, tier: str = "strict_pixel_blocking") -> ScreenFixtureEntry:
    return ScreenFixtureEntry(
        id=screen_id,
        layout="layouts/music_v2_layout.json",
        feature="music_v2",
        golden_id=screen_id,
        corpus_tier=tier,  # type: ignore[arg-type]
    )


def test_blocking_pass_when_all_screens_pass() -> None:
    passed = ScreenOracleResult(
        screen_id="music_v2",
        corpus_tier="strict_pixel_blocking",
        blocking_pass=True,
        metrics=ScreenOracleMetrics(non_text_pixel_diff=0.01, geometry_iou=0.99),
    )
    with patch(
        "figma_flutter_agent.validation.oracle.runner.load_screens_manifest",
    ) as load_manifest:
        load_manifest.return_value.screens = [_entry("music_v2")]
        with patch(
            "figma_flutter_agent.validation.oracle.runner.evaluate_screen_oracle",
            return_value=passed,
        ):
            report = run_corpus_oracle()
    assert report.blocking_passed
    assert report.full_corpus_passed


def test_blocking_fail_when_pixel_regresses() -> None:
    failed = ScreenOracleResult(
        screen_id="music_v2",
        corpus_tier="strict_pixel_blocking",
        blocking_pass=False,
        failures=("non-text pixel gate failed",),
        metrics=ScreenOracleMetrics(non_text_pixel_diff=0.2),
    )
    with patch(
        "figma_flutter_agent.validation.oracle.runner.load_screens_manifest",
    ) as load_manifest:
        load_manifest.return_value.screens = [_entry("music_v2")]
        with patch(
            "figma_flutter_agent.validation.oracle.runner.evaluate_screen_oracle",
            return_value=failed,
        ):
            report = run_corpus_oracle()
    assert not report.blocking_passed


def test_advisory_text_region_failure_does_not_block_release() -> None:
    advisory = ScreenOracleResult(
        screen_id="bounded_order_card",
        corpus_tier="advisory_pixel",
        blocking_pass=True,
        advisory_pass=False,
        metrics=ScreenOracleMetrics(text_region_pixel_diff=0.5),
    )
    blocking = ScreenOracleResult(
        screen_id="music_v2",
        corpus_tier="strict_pixel_blocking",
        blocking_pass=True,
        metrics=ScreenOracleMetrics(non_text_pixel_diff=0.01, geometry_iou=1.0),
    )
    with patch(
        "figma_flutter_agent.validation.oracle.runner.load_screens_manifest",
    ) as load_manifest:
        load_manifest.return_value.screens = [
            _entry("music_v2"),
            ScreenFixtureEntry(
                id="bounded_order_card",
                layout="layouts/bounded_order_card.json",
                feature="bounded_order_card",
                corpus_tier="advisory_pixel",
                thresholds=OracleThresholds(),
            ),
        ]
        with patch(
            "figma_flutter_agent.validation.oracle.runner.evaluate_screen_oracle",
            side_effect=[blocking, advisory],
        ):
            report = run_corpus_oracle()
    assert report.blocking_passed
    assert report.advisory_only_failures == 1
    assert not report.full_corpus_passed
