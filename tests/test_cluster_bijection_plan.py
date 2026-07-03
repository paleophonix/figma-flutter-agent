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


def _minimal_node(
    node_id: str,
    *,
    cluster_id: str | None = None,
    children: list[CleanDesignTreeNode] | None = None,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="n",
        type=NodeType.CONTAINER,
        children=children or [],
        cluster_id=cluster_id,
    )


def _spec(cluster_id: str, class_name: str, rep_id: str) -> ClusterWidgetSpec:
    return ClusterWidgetSpec(
        cluster_id=cluster_id,
        class_name=class_name,
        file_name=f"{class_name.lower()}.dart",
        representative=_minimal_node(rep_id),
    )


def _screen_with_usages(*usages: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return _minimal_node("screen", children=list(usages))


def test_bijection_shadow_ok_for_unique_specs() -> None:
    specs = [_spec("c1", "FooWidget", "n1"), _spec("c2", "BarWidget", "n2")]
    trees = [
        _screen_with_usages(
            _minimal_node("use_c1", cluster_id="c1"),
            _minimal_node("use_c2", cluster_id="c2"),
        ),
    ]
    plan = ClusterExtractionPlan.from_specs_and_trees(specs, trees)
    report = validate_extraction_bijection_shadow(plan)
    assert report.ok is True


def test_bijection_shadow_many_callsites_one_definition() -> None:
    specs = [_spec("c1", "FooWidget", "rep_c1")]
    trees = [
        _screen_with_usages(
            _minimal_node("use_a", cluster_id="c1"),
            _minimal_node("use_b", cluster_id="c1"),
        ),
    ]
    plan = ClusterExtractionPlan.from_specs_and_trees(specs, trees)
    key = plan.definitions[0]
    assert plan.callsite_to_definition["use_a"] == key
    assert plan.callsite_to_definition["use_b"] == key
    report = validate_extraction_bijection_shadow(plan)
    assert report.ok is True
    assert not any(item.code == "duplicate_definition" for item in report.diagnostics)


def test_bijection_shadow_orphan_definition_without_callsite() -> None:
    specs = [_spec("c1", "FooWidget", "rep_c1")]
    plan = ClusterExtractionPlan.from_specs_and_trees(specs, [])
    report = validate_extraction_bijection_shadow(plan)
    assert report.ok is False
    assert any(item.code == "orphan_definition" for item in report.diagnostics)


def test_enforce_blocked_without_m3_authority() -> None:
    specs = [_spec("c1", "FooWidget", "n1")]
    trees = [_screen_with_usages(_minimal_node("use_c1", cluster_id="c1"))]
    plan = ClusterExtractionPlan.from_specs_and_trees(specs, trees)
    with pytest.raises(RuntimeError, match="requires FIGMA_M3"):
        enforce_extraction_bijection(plan)


def test_enforce_blocked_without_m2_closure_even_when_mode_enforce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [_spec("c1", "FooWidget", "n1")]
    trees = [_screen_with_usages(_minimal_node("use_c1", cluster_id="c1"))]
    plan = ClusterExtractionPlan.from_specs_and_trees(specs, trees)
    monkeypatch.setenv("FIGMA_M3_BIJECTION_MODE", "enforce")
    with pytest.raises(RuntimeError, match="M2 closure"):
        enforce_extraction_bijection(plan)


def test_definition_key_shadow_report() -> None:
    specs = [_spec("c1", "FooWidget", "n1")]
    report = compare_definition_key_shadow(specs)
    assert report.legacy_map["c1"] == "FooWidget"
    assert not report.mismatches


def test_bijection_plan_dependencies_nested_cluster() -> None:
    nested_usage = _minimal_node("nested_usage", cluster_id="c_child")
    outer_rep = _minimal_node("outer_rep", children=[nested_usage])
    specs = [
        ClusterWidgetSpec(
            cluster_id="c_parent",
            class_name="ParentWidget",
            file_name="parentwidget.dart",
            representative=outer_rep,
        ),
        ClusterWidgetSpec(
            cluster_id="c_child",
            class_name="ChildWidget",
            file_name="childwidget.dart",
            representative=nested_usage,
        ),
    ]
    trees = [
        _screen_with_usages(
            _minimal_node("parent_usage", cluster_id="c_parent"),
            nested_usage,
        ),
    ]
    plan = ClusterExtractionPlan.from_specs_and_trees(specs, trees)
    parent_key = next(key for key in plan.definitions if key.cluster_id == "c_parent")
    child_key = next(key for key in plan.definitions if key.cluster_id == "c_child")
    assert child_key in plan.dependencies[parent_key]


def test_bijection_shadow_detects_dependency_cycle() -> None:
    a_usage = _minimal_node("use_a", cluster_id="c_a")
    b_usage = _minimal_node("use_b", cluster_id="c_b")
    a_rep = _minimal_node("rep_a", children=[b_usage])
    b_rep = _minimal_node("rep_b", children=[a_usage])
    specs = [
        ClusterWidgetSpec(
            cluster_id="c_a",
            class_name="AWidget",
            file_name="a.dart",
            representative=a_rep,
        ),
        ClusterWidgetSpec(
            cluster_id="c_b",
            class_name="BWidget",
            file_name="b.dart",
            representative=b_rep,
        ),
    ]
    trees = [_screen_with_usages(a_usage, b_usage)]
    plan = ClusterExtractionPlan.from_specs_and_trees(specs, trees)
    report = validate_extraction_bijection_shadow(plan)
    assert report.ok is False
    assert any(item.code == "delegate_dependency_cycle" for item in report.diagnostics)


def test_bijection_shadow_detects_self_cycle() -> None:
    inner = _minimal_node("inner_self", cluster_id="c_self")
    rep = _minimal_node("rep_self", children=[inner])
    specs = [
        ClusterWidgetSpec(
            cluster_id="c_self",
            class_name="SelfWidget",
            file_name="self.dart",
            representative=rep,
        ),
    ]
    trees = [_screen_with_usages(_minimal_node("use_self", cluster_id="c_self"))]
    plan = ClusterExtractionPlan.from_specs_and_trees(specs, trees)
    report = validate_extraction_bijection_shadow(plan)
    assert report.ok is False
    assert any(item.code == "delegate_dependency_cycle" for item in report.diagnostics)


def test_bijection_plan_shape_members_are_callsites() -> None:
    member = _minimal_node("shape_member", cluster_id="c1")
    spec = ClusterWidgetSpec(
        cluster_id="c1",
        class_name="FooWidget",
        file_name="foo.dart",
        representative=_minimal_node("rep"),
        shape_members=(member,),
    )
    plan = ClusterExtractionPlan.from_specs_and_trees([spec], [])
    assert plan.callsite_to_definition["shape_member"] == plan.definitions[0]


def test_bijection_two_topology_variants_same_cluster_id() -> None:
    """Cross-variant dependency uses node-id map, not cluster_id last-wins."""
    usage_b = _minimal_node("usage_b", cluster_id="c_x")
    rep_a = _minimal_node("rep_a", children=[usage_b])
    rep_b = _minimal_node("rep_b")
    specs = [
        ClusterWidgetSpec(
            cluster_id="c_x",
            class_name="VariantAWidget",
            file_name="a.dart",
            representative=rep_a,
        ),
        ClusterWidgetSpec(
            cluster_id="c_x",
            class_name="VariantBWidget",
            file_name="b.dart",
            representative=rep_b,
        ),
    ]
    trees = [_screen_with_usages(_minimal_node("usage_a", cluster_id="c_x"))]
    plan = ClusterExtractionPlan.from_specs_and_trees(specs, trees)
    assert len(plan.definitions) == 2
    key_a = next(k for k in plan.definitions if k.representative_node_id == "rep_a")
    key_b = next(k for k in plan.definitions if k.representative_node_id == "rep_b")
    assert key_b in plan.dependencies[key_a]
