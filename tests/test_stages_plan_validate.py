"""Tests for plan and validate pipeline stages."""

import json
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.planner import GenerationPlanContext, plan_from_figma_root
from figma_flutter_agent.parser.tokens import build_design_tokens
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.stages.plan import PlanStageRequest, plan_generation_output
from figma_flutter_agent.stages.validate import ValidateStageRequest, validate_planned_generation


def test_plan_generation_output_matches_planner() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    settings = Settings()
    tree, _, _, cluster_summary = build_clean_tree(root)
    tokens = build_design_tokens(root, None)
    direct = plan_from_figma_root(root, settings, node_id=root["id"])

    context = GenerationPlanContext(
        settings=settings,
        clean_tree=tree,
        tokens=tokens,
        resolved_feature="onboarding_screen",
        node_id=root["id"],
        cluster_summary=cluster_summary,
        figma_root=root,
    )
    planned = plan_generation_output(PlanStageRequest(context=context)).planned_files

    assert set(planned.keys()) == set(direct.keys())


def test_validate_planned_generation_passes_for_fixture_plan() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    settings = Settings()
    planned = plan_from_figma_root(root, settings, node_id=root["id"])
    tree, _, _, _ = build_clean_tree(root)

    result = validate_planned_generation(
        ValidateStageRequest(
            planned_files=planned,
            clean_trees=[tree],
            responsive_enabled=settings.agent.responsive.enabled,
            avoid_fixed_sizes=settings.agent.layout.avoid_fixed_sizes,
        )
    )

    assert isinstance(result.warnings, list)


def test_validate_planned_generation_raises_without_text_scaler() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.CONTAINER)
    planned = {
        "lib/features/home/home_screen.dart": """
class HomeScreen extends StatelessWidget {
  Widget build(BuildContext context) {
    return GeneratedScreenShell(child: const Text('Home'));
  }
}
""",
    }

    with pytest.raises(GenerationError, match="textScalerOf"):
        validate_planned_generation(
            ValidateStageRequest(
                planned_files=planned,
                clean_trees=[tree],
                responsive_enabled=True,
                avoid_fixed_sizes=False,
            )
        )
