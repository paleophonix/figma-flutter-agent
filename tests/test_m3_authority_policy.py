"""Tests for M3 policy and central authority gate."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.compiler.m3_authority import route_enforce_enabled
from figma_flutter_agent.compiler.m3_policy import M3Policy, M3RouteMode
from figma_flutter_agent.generator.extraction.definition_key import (
    DefinitionKey,
    lookup_cluster_class_authoritative,
)


def test_route_enforce_requires_m2_and_authority_flag() -> None:
    policy = M3Policy(
        m2_closed=False,
        authority_enabled=False,
        definition_key_mode=M3RouteMode.ENFORCE,
    )
    assert route_enforce_enabled("definition_key", policy) is False

    policy_half = M3Policy(
        m2_closed=True,
        authority_enabled=False,
        definition_key_mode=M3RouteMode.ENFORCE,
    )
    assert route_enforce_enabled("definition_key", policy_half) is False

    policy_full = M3Policy(
        m2_closed=True,
        authority_enabled=True,
        definition_key_mode=M3RouteMode.ENFORCE,
    )
    assert route_enforce_enabled("definition_key", policy_full) is True


def test_definition_key_lookup_respects_central_gate() -> None:
    key = DefinitionKey(cluster_id="c1", topology_variant="default", representative_node_id="n1")
    shadow = {key: "ShadowWidget"}
    legacy = {"c1": "LegacyWidget"}

    blocked = M3Policy(definition_key_mode=M3RouteMode.ENFORCE)
    assert lookup_cluster_class_authoritative(shadow, legacy, key=key, policy=blocked) == "LegacyWidget"

    enabled = M3Policy(
        m2_closed=True,
        authority_enabled=True,
        definition_key_mode=M3RouteMode.ENFORCE,
    )
    assert lookup_cluster_class_authoritative(shadow, legacy, key=key, policy=enabled) == "ShadowWidget"


def test_inference_callsite_via_extracted_widget_ref() -> None:
    from figma_flutter_agent.generator.extraction.bijection_plan import (
        ClusterExtractionPlan,
        validate_extraction_bijection_shadow,
    )
    from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

    node = CleanDesignTreeNode(
        id="inf_node",
        name="card",
        type=NodeType.CONTAINER,
        children=[],
    )
    node.extracted_widget_ref = "InferredCardWidget"
    spec = ClusterWidgetSpec(
        cluster_id="semantic_inf_node",
        class_name="InferredCardWidget",
        file_name="inferredcard.dart",
        representative=node,
        source_kind="inference",
    )
    trees = [
        CleanDesignTreeNode(id="screen", name="s", type=NodeType.CONTAINER, children=[node]),
    ]
    plan = ClusterExtractionPlan.from_specs_and_trees([spec], trees)
    assert plan.callsite_to_definition["inf_node"] == plan.definitions[0]
    assert validate_extraction_bijection_shadow(plan).ok is True


def test_compiler_modules_do_not_read_env_for_m3() -> None:
    repo = Path(__file__).resolve().parents[1]
    roots = (
        repo / "src/figma_flutter_agent/generator/extraction",
        repo / "src/figma_flutter_agent/generator/geometry",
    )
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "os.environ" in text or "m3_policy_from_env" in text:
                offenders.append(str(path.relative_to(repo)))
    assert offenders == []


def test_m2_closure_record_blocks_authority_without_closed_status() -> None:
    from figma_flutter_agent.compiler.m3_policy import is_m2_closure_closed, m3_policy_at_pipeline_boundary

    assert is_m2_closure_closed() is False
    policy = m3_policy_at_pipeline_boundary()
    assert policy.m2_closed is False
    assert policy.authority_enabled is False


def test_active_m3_policy_context_binding() -> None:
    from figma_flutter_agent.compiler.m3_policy import (
        M3RouteMode,
        active_m3_policy,
        bind_m3_policy,
        reset_m3_policy,
    )

    custom = M3Policy(geometry_slots_mode=M3RouteMode.SHADOW)
    token = bind_m3_policy(custom)
    try:
        assert active_m3_policy() is custom
    finally:
        reset_m3_policy(token)
