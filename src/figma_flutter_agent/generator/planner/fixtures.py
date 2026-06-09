"""Fixture-driven entry point for the generation planner."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.layout.common import to_snake_case
from figma_flutter_agent.generator.planner.context import GenerationPlanContext
from figma_flutter_agent.generator.planner.plan import plan_generation_files
from figma_flutter_agent.parser.tokens.build import build_design_tokens
from figma_flutter_agent.parser.tree import build_clean_tree


def plan_from_figma_root(
    root: dict[str, Any],
    settings: Settings,
    *,
    node_id: str = "1:1",
    feature_name: str | None = None,
    package_name: str = "demo_app",
) -> dict[str, str]:
    """Plan deterministic outputs from a local Figma node JSON fixture.

    Args:
        root: Figma frame node dictionary.
        settings: Agent settings controlling generation mode.
        node_id: Node id used for route metadata.
        feature_name: Optional feature folder override.
        package_name: Flutter package name for optional golden test scaffold.

    Returns:
        Planned generated files keyed by relative path.
    """
    tokens = build_design_tokens(root, None)
    clean_tree, _, _, cluster_summary = build_clean_tree(root)
    configured_feature = feature_name or settings.agent.naming.feature_name
    if configured_feature != "auto":
        resolved_feature = to_snake_case(configured_feature)
    else:
        resolved_feature = to_snake_case(clean_tree.name)

    context = GenerationPlanContext(
        settings=settings,
        clean_tree=clean_tree,
        tokens=tokens,
        resolved_feature=resolved_feature,
        node_id=node_id,
        cluster_summary=cluster_summary,
        figma_root=root,
        package_name=package_name,
    )
    return plan_generation_files(context)
