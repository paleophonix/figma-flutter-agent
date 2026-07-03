"""Tests for cluster extraction bijection plan (04-P0-3)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.generator.extraction.bijection_plan import (
    ClusterExtractionPlan,
    enforce_extraction_bijection,
    validate_extraction_bijection_shadow,
)
from figma_flutter_agent.generator.extraction.definition_key import compare_definition_key_shadow
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _minimal_node(node_id: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(id=node_id, name="n", type=NodeType.CONTAINER, children=[])


def _spec(cluster_id: str, class_name: str, rep_id: str) -> ClusterWidgetSpec:
    return ClusterWidgetSpec(
        cluster_id=cluster_id,
        class_name=class_name,
        file_name=f"{class_name.lower()}.dart",
        representative=_minimal_node(rep_id),
    )


def test_bijection_shadow_ok_for_unique_specs() -> None:
    specs = [_spec("c1", "FooWidget", "n1"), _spec("c2", "BarWidget", "n2")]
    plan = ClusterExtractionPlan.from_specs(specs)
    report = validate_extraction_bijection_shadow(plan)
    assert report.ok is True


def test_bijection_shadow_duplicate_callsite() -> None:
    specs = [_spec("c1", "FooWidget", "same"), _spec("c2", "BarWidget", "same")]
    plan = ClusterExtractionPlan.from_specs(specs)
    report = validate_extraction_bijection_shadow(plan)
    assert report.ok is False
    assert any(item.code == "duplicate_callsite" for item in report.diagnostics)


def test_enforce_blocked_without_m3_authority() -> None:
    specs = [_spec("c1", "FooWidget", "n1")]
    plan = ClusterExtractionPlan.from_specs(specs)
    with pytest.raises(RuntimeError, match="M3 authority"):
        enforce_extraction_bijection(plan)


def test_definition_key_shadow_report() -> None:
    specs = [_spec("c1", "FooWidget", "n1")]
    report = compare_definition_key_shadow(specs)
    assert report.legacy_map["c1"] == "FooWidget"
    assert not report.mismatches
