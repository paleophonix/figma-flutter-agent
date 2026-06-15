"""Plan stage for mapping parsed design data to generated Dart files."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.planner import GenerationPlanContext, plan_generation_files


@dataclass
class PlanStageRequest:
    """Inputs required to plan generated Dart files."""

    context: GenerationPlanContext


@dataclass
class PlanStageResult:
    """Output of the generation planning stage."""

    planned_files: dict[str, str]


def plan_generation_output(request: PlanStageRequest) -> PlanStageResult:
    """Plan all generated Dart files for a pipeline run.

    Args:
        request: Parsed design data, settings, and optional LLM output.

    Returns:
        Mapping of relative project paths to generated file contents.
    """
    from figma_flutter_agent.generator.pixel_policy import pixel_generation_policy_scope

    generation = request.context.settings.agent.generation
    with pixel_generation_policy_scope(generation):
        return PlanStageResult(planned_files=plan_generation_files(request.context))
