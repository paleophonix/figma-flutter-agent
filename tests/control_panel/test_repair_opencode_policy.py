"""Tests for control-panel OpenCode policy helpers."""

from __future__ import annotations

from control_panel.repair.opencode.policy import (
    CP_OPENCODE_BUILD_AGENT,
    CP_OPENCODE_READ_AGENT,
    resolve_cp_prompt_kwargs,
)
from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig


def test_resolve_cp_read_stage_uses_plan_agent_and_pipeline_effort() -> None:
    config = DebugPipelineConfig(effort="high", models={"single": "deepseek/deepseek-v4-pro"})
    kwargs = resolve_cp_prompt_kwargs(stage="diagnose", stage_model="", pipeline=config)
    assert kwargs["agent"] == CP_OPENCODE_READ_AGENT
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["model"] == "openrouter/deepseek/deepseek-v4-pro"


def test_resolve_cp_build_stage_uses_repair_agent() -> None:
    config = DebugPipelineConfig()
    kwargs = resolve_cp_prompt_kwargs(
        stage="build",
        stage_model="custom/vendor-model",
        pipeline=config,
    )
    assert kwargs["agent"] == CP_OPENCODE_BUILD_AGENT
    assert kwargs["model"] == "openrouter/custom/vendor-model"


def test_resolve_cp_stage_model_override() -> None:
    config = DebugPipelineConfig(models={"single": "deepseek/deepseek-v4-pro"})
    kwargs = resolve_cp_prompt_kwargs(
        stage="review",
        stage_model="moonshotai/kimi-k2.7-code",
        pipeline=config,
    )
    assert kwargs["model"] == "openrouter/moonshotai/kimi-k2.7-code"
