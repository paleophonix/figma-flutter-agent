import json
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.layout.common import to_snake_case
from figma_flutter_agent.generator.planner import (
    GenerationPlanContext,
    plan_from_figma_root,
    plan_generation_files,
)
from figma_flutter_agent.parser.tokens.build import build_design_tokens
from figma_flutter_agent.parser.tree import build_clean_tree


def test_plan_from_figma_root_includes_layout_screen_and_theme() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, Settings(), node_id=root["id"])

    assert "lib/generated/onboarding_screen_layout.dart" in planned
    assert "test/capture/onboarding_screen_screen_capture_test.dart" in planned
    assert "lib/theme/app_colors.dart" in planned
    assert "lib/main.dart" in planned


def test_generation_plan_context_is_reusable() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    settings = Settings()
    tokens = build_design_tokens(root, None)
    tree, _, _, cluster_summary = build_clean_tree(root)
    planned = plan_generation_files(
        GenerationPlanContext(
            settings=settings,
            clean_tree=tree,
            tokens=tokens,
            resolved_feature=to_snake_case(tree.name),
            node_id=root["id"],
            cluster_summary=cluster_summary,
            figma_root=root,
        )
    )

    assert planned["lib/generated/onboarding_screen_layout.dart"]
