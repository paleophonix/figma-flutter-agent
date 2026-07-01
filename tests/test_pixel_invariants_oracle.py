"""Pixel invariant promotion and corpus oracle contract (Wave E / U7)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from figma_flutter_agent.config.profiles import apply_pixel_fidelity_profile
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.fixtures.screens_manifest import load_screens_manifest
from figma_flutter_agent.generator.geometry.invariants.models import (
    geometry_violation,
    promote_soft_pixel_invariants_scope,
)
from figma_flutter_agent.generator.geometry.invariants.reporting import (
    raise_on_hard_geometry_violations,
)
from figma_flutter_agent.validation.oracle.models import ScreenOracleMetrics, ScreenOracleResult
from figma_flutter_agent.validation.oracle.runner import run_corpus_oracle


def test_pixel_profile_promotes_soft_invariants_to_hard() -> None:
    with promote_soft_pixel_invariants_scope(True):
        violation = geometry_violation(
            "t1_placement_aabb_width",
            "node-1",
            "width drift",
        )
        assert violation.severity == "hard"
        with pytest.raises(GenerationError, match="Geometry invariant"):
            raise_on_hard_geometry_violations([violation], context="test")

    soft = geometry_violation("t1_placement_aabb_width", "node-1", "width drift")
    assert soft.severity == "soft"
    raise_on_hard_geometry_violations([soft], context="test")


def test_pixel_fidelity_profile_enables_promotion_flag() -> None:
    settings = apply_pixel_fidelity_profile(Settings())
    assert settings.agent.generation.promote_soft_pixel_invariants is True


def test_pixel_fidelity_profile_oracle_contract() -> None:
    settings = apply_pixel_fidelity_profile(Settings())
    manifest = load_screens_manifest()
    blocking = [
        screen for screen in manifest.screens if screen.corpus_tier == "strict_pixel_blocking"
    ]
    assert blocking
    for entry in blocking:
        assert entry.thresholds.non_text_pixel_max > 0

    passed = ScreenOracleResult(
        screen_id=blocking[0].id,
        corpus_tier="strict_pixel_blocking",
        blocking_pass=True,
        metrics=ScreenOracleMetrics(non_text_pixel_diff=0.01, geometry_iou=0.99),
    )
    with (
        patch(
            "figma_flutter_agent.validation.oracle.runner.load_screens_manifest",
            return_value=manifest,
        ),
        patch(
            "figma_flutter_agent.validation.oracle.runner.evaluate_screen_oracle",
            return_value=passed,
        ),
    ):
        report = run_corpus_oracle(screen_ids=[blocking[0].id], settings=settings)
    assert report.blocking_passed
    assert settings.agent.generation.pixel_fidelity is True
