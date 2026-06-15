"""Promotion candidate evidence must match classified kinds per screen."""

from __future__ import annotations

from unittest.mock import patch

from figma_flutter_agent.fixtures.screens_manifest import ScreenFixtureEntry
from figma_flutter_agent.schemas.ir import WidgetIrKind
from figma_flutter_agent.validation.oracle.models import ScreenOracleMetrics, ScreenOracleResult
from figma_flutter_agent.validation.oracle.runner import run_corpus_oracle


def test_promotion_candidates_require_classified_kind_on_screen() -> None:
    entry = ScreenFixtureEntry(
        id="music_v2",
        layout="layouts/music_v2_layout.json",
        feature="music_v2",
        golden_id="music_v2",
        corpus_tier="strict_pixel_blocking",
    )
    passed = ScreenOracleResult(
        screen_id="music_v2",
        corpus_tier="strict_pixel_blocking",
        blocking_pass=True,
        metrics=ScreenOracleMetrics(non_text_pixel_diff=0.01, geometry_iou=1.0),
    )
    with patch(
        "figma_flutter_agent.validation.oracle.runner.load_screens_manifest",
    ) as load_manifest:
        load_manifest.return_value.screens = [entry]
        with (
            patch(
                "figma_flutter_agent.validation.oracle.runner.evaluate_screen_oracle",
                return_value=passed,
            ),
            patch(
                "figma_flutter_agent.validation.oracle.runner.classified_semantic_kinds_for_entry",
                return_value=frozenset({WidgetIrKind.BUTTON_FILLED}),
            ),
        ):
            report = run_corpus_oracle()
    kinds = {item.kind for item in report.promotion_candidates}
    assert "button_outlined" not in kinds
    assert all(item.screen_id == "music_v2" for item in report.promotion_candidates)
    if report.promotion_candidates:
        assert report.promotion_candidates[0].kind == "button_filled"
