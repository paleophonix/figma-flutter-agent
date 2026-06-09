"""Dart file generation planner package."""

from figma_flutter_agent.generator.planner.context import (
    GenerationPlanContext,
    _resolve_use_scaffold,
    _tree_has_layout_slots,
)
from figma_flutter_agent.generator.planner.fixtures import plan_from_figma_root
from figma_flutter_agent.generator.planner.plan import (
    plan_generation_files,
)

__all__ = [
    "GenerationPlanContext",
    "plan_generation_files",
    "plan_from_figma_root",
    "_resolve_use_scaffold",
    "_tree_has_layout_slots",
]
