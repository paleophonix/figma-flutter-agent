"""Resolve OpenCode repair step → OpenRouter model / Fusion invocation."""

from __future__ import annotations

from figma_flutter_agent.config.debug_pipeline import (
    DebugPipelineConfig,
    DebugPipelineStep,
)
from figma_flutter_agent.dev.opencode.fusion_escalation import build_escalation_panel
from figma_flutter_agent.llm.openrouter_fusion import (
    OpenRouterFusionInvocation,
    build_fusion_invocation,
    build_single_invocation,
)


def resolve_step_invocation(
    config: DebugPipelineConfig,
    step: DebugPipelineStep,
    *,
    board: str = "forensic",
    outer_round: int = 1,
) -> OpenRouterFusionInvocation:
    """Map a pipeline step to an OpenRouter model or Fusion escalation panel.

    Args:
        config: Loaded ``debug_pipeline`` policy from agent YAML.
        step: Pipeline step name.
        board: Agent board (``screen`` or ``forensic``) for board-aware overrides.
        outer_round: Outer correction loop index (1-based); round 2+ may use Fusion.

    Returns:
        Invocation descriptor (Fusion escalation or single slug).
    """
    if config.uses_fusion(step, outer_round=outer_round):
        base = config.model_for_step(step, board=board)
        return build_fusion_invocation(
            fusion_model=config.openrouter.fusion_model,
            judge_model=base,
            analysis_models=build_escalation_panel(
                base,
                config.board_models,
                outer_round,
            ),
        )
    return build_single_invocation(
        model=config.model_for_step(step, board=board),
    )
