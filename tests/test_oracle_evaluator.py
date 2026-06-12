"""Unit tests for per-screen corpus oracle evaluator."""

from __future__ import annotations

from unittest.mock import patch

from figma_flutter_agent.fixtures.screens_manifest import ScreenFixtureEntry
from figma_flutter_agent.validation.oracle.evaluator import (
    _needs_capture,
    evaluate_screen_oracle,
)


def test_semantic_only_skips_capture_by_default() -> None:
    entry = ScreenFixtureEntry(
        id="consent_checkbox",
        layout="layouts/consent_checkbox_row.json",
        feature="consent_checkbox",
        corpus_tier="semantic_only",
    )
    assert entry.oracle_modes == ["semantic"]
    assert not _needs_capture(entry)


def test_advisory_geometry_failure_marks_structural_advisory_fail() -> None:
    entry = ScreenFixtureEntry(
        id="bounded_order_card",
        layout="layouts/bounded_order_card.json",
        feature="bounded_order_card",
        corpus_tier="advisory_pixel",
    )
    geometry_result = type(
        "GeometryResult",
        (),
        {"skipped": False, "ok": False, "reason": "geometry gate failed", "min_iou_observed": 0.5},
    )()
    pixel_result = type(
        "PixelResult",
        (),
        {
            "skipped": False,
            "ok": True,
            "non_text_pixel_diff": 0.01,
            "text_region_pixel_diff": 0.01,
            "text_bounds_delta": 0.0,
            "reason": None,
        },
    )()
    with (
        patch("figma_flutter_agent.validation.oracle.evaluator.FixtureCaptureBatch") as batch_cls,
        patch(
            "figma_flutter_agent.validation.oracle.evaluator.compare_fixture_golden",
            return_value=pixel_result,
        ),
        patch(
            "figma_flutter_agent.validation.oracle.evaluator.check_fixture_geometry",
            return_value=geometry_result,
        ),
    ):
        batch_cls.return_value.capture_fixture_entry.return_value = None
        result = evaluate_screen_oracle(entry)
    assert result.advisory_pass is False
    assert result.advisory_text_pass is True
