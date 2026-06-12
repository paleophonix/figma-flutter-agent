"""Corpus oracle dev-vs-production profile comparison."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from figma_flutter_agent.config import Settings
from figma_flutter_agent.fixtures.screens_manifest import ScreenFixtureEntry
from figma_flutter_agent.generator.geometry.invariants.models import geometry_violation
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.validation.oracle.profile_compare import (
    ProfileComparisonReport,
    compare_profile_soft_invariants,
)
from figma_flutter_agent.validation.oracle.reports import write_profile_comparison_json


def _entry(screen_id: str = "screen") -> ScreenFixtureEntry:
    return ScreenFixtureEntry(
        id=screen_id,
        layout="layouts/screen.json",
        feature="screen",
    )


def _tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(id="root", name="Root", type=NodeType.STACK)


def test_compare_profiles_fails_when_production_soft_count_grows() -> None:
    soft = geometry_violation(
        code="inv_text_metrics",
        node_id="input",
        detail="estimated input metrics",
    )
    with (
        patch(
            "figma_flutter_agent.validation.oracle.profile_compare.load_screens_manifest",
            return_value=SimpleNamespace(screens=[_entry()]),
        ),
        patch(
            "figma_flutter_agent.validation.oracle.profile_compare.load_layout_tree",
            return_value=_tree(),
        ),
        patch(
            "figma_flutter_agent.validation.oracle.profile_compare.normalize_clean_tree",
            side_effect=lambda tree, **_: tree,
        ),
        patch(
            "figma_flutter_agent.validation.oracle.profile_compare.validate_geometry_invariants",
            side_effect=[[], [soft]],
        ),
    ):
        report = compare_profile_soft_invariants(settings=Settings())

    assert not report.passed
    assert report.results[0].regressions == {"inv_text_metrics": {"dev": 0, "production": 1}}


def test_compare_profiles_passes_when_production_does_not_increase_soft_counts() -> None:
    soft = geometry_violation(
        code="inv_text_metrics",
        node_id="input",
        detail="estimated input metrics",
    )
    with (
        patch(
            "figma_flutter_agent.validation.oracle.profile_compare.load_screens_manifest",
            return_value=SimpleNamespace(screens=[_entry()]),
        ),
        patch(
            "figma_flutter_agent.validation.oracle.profile_compare.load_layout_tree",
            return_value=_tree(),
        ),
        patch(
            "figma_flutter_agent.validation.oracle.profile_compare.normalize_clean_tree",
            side_effect=lambda tree, **_: tree,
        ),
        patch(
            "figma_flutter_agent.validation.oracle.profile_compare.validate_geometry_invariants",
            side_effect=[[soft], [soft]],
        ),
    ):
        report = compare_profile_soft_invariants(settings=Settings())

    assert report.passed
    assert report.results[0].regressions == {}


def test_write_profile_comparison_json(tmp_path) -> None:
    report = ProfileComparisonReport(passed=True, results=())
    path = tmp_path / "profile_comparison.json"

    write_profile_comparison_json(report, path)

    assert '"passed": true' in path.read_text(encoding="utf-8")
