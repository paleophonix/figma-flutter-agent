"""Control-plane OpenCode prompt policy (``debug_pipeline`` + per-stage overrides)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig
from figma_flutter_agent.dev.opencode.opencode_policy import (
    OPENCODE_FIX_AGENT,
    OPENCODE_REPAIR_AGENT,
    build_opencode_overlay,
    normalize_opencode_model,
    opencode_reasoning_effort_value,
)

CP_OPENCODE_READ_AGENT = "plan"
CP_OPENCODE_BUILD_AGENT = OPENCODE_REPAIR_AGENT
CP_OPENCODE_FIX_AGENT = OPENCODE_FIX_AGENT

CP_STAGE_AGENTS: dict[str, str] = {
    "diagnose": CP_OPENCODE_READ_AGENT,
    "plan": CP_OPENCODE_READ_AGENT,
    "review": CP_OPENCODE_READ_AGENT,
    "build": CP_OPENCODE_BUILD_AGENT,
    "fix": CP_OPENCODE_FIX_AGENT,
}


def load_debug_pipeline_from_agent_repo(agent_repo: Path) -> DebugPipelineConfig:
    """Load ``debug_pipeline`` policy from the agent repo YAML."""
    config_path = agent_repo / ".ai-figma-flutter.yml"
    return load_settings(config_path).agent.debug_pipeline


def resolve_cp_model(*, stage_model: str, pipeline: DebugPipelineConfig) -> str:
    """Resolve OpenCode model slug for one CP repair stage."""
    slug = stage_model.strip() or pipeline.models.single
    return normalize_opencode_model(slug)


def resolve_cp_prompt_kwargs(
    *,
    stage: str,
    stage_model: str,
    pipeline: DebugPipelineConfig,
) -> dict[str, str | None]:
    """Return OpenCode transport kwargs for a legacy CP repair stage."""
    agent = CP_STAGE_AGENTS.get(stage)
    if agent is None:
        msg = f"unknown CP OpenCode stage: {stage}"
        raise ValueError(msg)
    return {
        "agent": agent,
        "model": resolve_cp_model(stage_model=stage_model, pipeline=pipeline),
        "reasoning_effort": opencode_reasoning_effort_value(pipeline.effort),
    }


__all__ = [
    "CP_OPENCODE_BUILD_AGENT",
    "CP_OPENCODE_FIX_AGENT",
    "CP_OPENCODE_READ_AGENT",
    "build_opencode_overlay",
    "load_debug_pipeline_from_agent_repo",
    "resolve_cp_model",
    "resolve_cp_prompt_kwargs",
]
