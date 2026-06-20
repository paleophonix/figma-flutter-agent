"""Resolve OpenCode repair step → OpenRouter model / Fusion invocation."""

from __future__ import annotations

from figma_flutter_agent.config.debug_pipeline import (
    ENSEMBLE_STEPS,
    DebugPipelineConfig,
    DebugPipelineStep,
)
from figma_flutter_agent.llm.openrouter_fusion import (
    OpenRouterFusionInvocation,
    build_fusion_invocation,
    build_single_invocation,
)


def resolve_step_invocation(
    config: DebugPipelineConfig,
    step: DebugPipelineStep,
) -> OpenRouterFusionInvocation:
    """Map a pipeline step to an OpenRouter model or Fusion panel.

    Args:
        config: Loaded ``debug_pipeline`` policy from agent YAML.
        step: Pipeline step name.

    Returns:
        Invocation descriptor (Fusion for ensemble steps when enabled, else single slug).
    """
    if config.uses_fusion(step):
        return build_fusion_invocation(
            fusion_model=config.openrouter.fusion_model,
            judge_model=config.openrouter.judge_model,
            analysis_models=config.panel_for_step(step),
        )
    return build_single_invocation(model=config.single_model_for_step(step))


def ensemble_steps(config: DebugPipelineConfig) -> frozenset[DebugPipelineStep]:
    """Return steps that may use Fusion for the current config."""
    if not config.ensemble.enabled:
        return frozenset()
    return ENSEMBLE_STEPS
