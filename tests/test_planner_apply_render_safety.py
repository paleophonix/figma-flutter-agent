"""Planner render-safety consolidation (T0.1 — no render_safety module)."""

from __future__ import annotations

from unittest.mock import patch

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.generator.planner import GenerationPlanContext, plan_generation_files
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    NodeType,
    Sizing,
    StackPlacement,
)


def _minimal_context(settings: Settings | None = None) -> GenerationPlanContext:
    settings = settings or Settings(
        agent=AgentYamlConfig(generation=GenerationConfig()),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="btn",
                name="CTA",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(
                    left=10.0,
                    top=10.0,
                    width=16.0,
                    height=16.0,
                ),
            ),
        ],
    )
    return GenerationPlanContext(
        settings=settings,
        clean_tree=root,
        tokens=DesignTokens(),
        resolved_feature="planner_safety",
        node_id="root",
        cluster_summary={},
    )


def test_plan_generation_files_without_render_safety_module_import() -> None:
    """Default flags must plan layout without importing generator.render_safety."""
    context = _minimal_context()
    with patch(
        "figma_flutter_agent.generator.planner.plan.render_layout_file",
        return_value={
            "lib/generated/planner_safety_layout.dart": "class X {}",
        },
    ) as render_mock:
        files = plan_generation_files(context)
    assert "lib/generated/planner_safety_layout.dart" in files
    render_mock.assert_called_once()
    kwargs = render_mock.call_args.kwargs
    assert kwargs.get("skip_layout_reconcile") is True


def test_plan_applies_min_touch_when_guards_enabled() -> None:
    context = _minimal_context()
    assert context.clean_tree.children[0].min_touch_target is None
    with patch(
        "figma_flutter_agent.generator.planner.plan.render_layout_file",
        return_value={"lib/generated/planner_safety_layout.dart": ""},
    ):
        plan_generation_files(context)
    assert context.clean_tree.children[0].min_touch_target == 44.0
