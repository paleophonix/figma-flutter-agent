"""OpenCode debug pipeline helpers."""

from __future__ import annotations

from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig, DebugPipelineStep
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.dev.opencode.client import OpenCodeClient
from figma_flutter_agent.dev.opencode.model_policy import resolve_step_invocation
from figma_flutter_agent.dev.opencode.opencode_policy import (
    build_opencode_overlay,
    overlay_json,
)
from figma_flutter_agent.dev.opencode.pipeline import PipelineOutcome, run_repair_pipeline
from figma_flutter_agent.dev.opencode.run_gate import RunGateResult, evaluate_run_gate
from figma_flutter_agent.dev.opencode.runtime import ensure_opencode_serve
from figma_flutter_agent.llm.clients.openrouter import OpenRouterLlmClient
from figma_flutter_agent.llm.openrouter_fusion import OpenRouterFusionInvocation

__all__ = [
    "DebugPipelineConfig",
    "DebugPipelineStep",
    "OpenCodeClient",
    "OpenRouterFusionInvocation",
    "OpenRouterLlmClient",
    "PipelineOutcome",
    "RunGateResult",
    "build_opencode_overlay",
    "create_openrouter_debug_client",
    "debug_pipeline_config",
    "ensure_opencode_serve",
    "evaluate_run_gate",
    "overlay_json",
    "resolve_step_invocation",
    "run_repair_pipeline",
]


def debug_pipeline_config(settings: Settings) -> DebugPipelineConfig:
    """Return loaded ``debug_pipeline`` policy from agent settings."""
    return settings.agent.debug_pipeline


def create_openrouter_debug_client(
    settings: Settings,
    *,
    step: DebugPipelineStep,
    board: str = "forensic",
    outer_round: int = 1,
) -> tuple[OpenRouterLlmClient, OpenRouterFusionInvocation]:
    """Build an OpenRouter client configured for one repair pipeline step."""
    from figma_flutter_agent.errors import LlmError

    api_key = settings.openrouter_api_key.get_secret_value().strip()
    if not api_key:
        raise LlmError("OPENROUTER_API_KEY is required for debug_pipeline OpenRouter calls")
    pipeline = debug_pipeline_config(settings)
    invocation = resolve_step_invocation(pipeline, step, board=board, outer_round=outer_round)
    client = OpenRouterLlmClient(
        api_key=api_key,
        model=invocation.model,
        strict_json_schema=False,
        temperature=settings.llm_temperature,
        top_p=settings.llm_top_p,
        reasoning=pipeline.reasoning_settings_for_step(step),
        max_retries=settings.llm_max_retries,
        max_output_tokens=settings.llm_max_output_tokens,
    )
    return client, invocation
