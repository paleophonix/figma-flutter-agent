"""Tests for debug_pipeline model policy and OpenRouter Fusion payloads."""

from __future__ import annotations

import pytest

from figma_flutter_agent.config import AgentYamlConfig, load_settings
from figma_flutter_agent.config.debug_pipeline import (
    DEFAULT_BOARD_MODELS,
    DEFAULT_EFFORT_PER_STEP,
    DEFAULT_SINGLE_MODEL,
    FUSION_OUTER_MODEL,
    DebugPipelineConfig,
    DebugPipelineModelsConfig,
)
from figma_flutter_agent.dev.opencode.model_policy import resolve_step_invocation
from figma_flutter_agent.dev.opencode.opencode_policy import prompt_options_for_write_step
from figma_flutter_agent.llm.openrouter_fusion import build_fusion_invocation


def test_debug_pipeline_defaults_embedded_in_agent_yaml() -> None:
    agent = AgentYamlConfig()
    pipeline = agent.debug_pipeline
    assert pipeline.effort == "high"
    assert pipeline.common_effort is False
    assert pipeline.reasoning_settings().effort == "high"
    assert pipeline.effort_for_step("inspect") == DEFAULT_EFFORT_PER_STEP["inspect"]
    assert pipeline.effort_for_step("diagnose") == "high"
    assert pipeline.openrouter.fusion_model == FUSION_OUTER_MODEL
    assert pipeline.board_models == DEFAULT_BOARD_MODELS
    assert pipeline.min_board_models == 2
    assert pipeline.max_board_models == 4
    assert pipeline.models.single == DEFAULT_SINGLE_MODEL


def test_common_effort_uses_global_effort_for_every_step() -> None:
    pipeline = DebugPipelineConfig(effort="low", common_effort=True)
    for step in DEFAULT_EFFORT_PER_STEP:
        assert pipeline.effort_for_step(step) == "low"  # type: ignore[arg-type]


def test_effort_per_step_override() -> None:
    pipeline = DebugPipelineConfig(
        effort_escalation={"enabled": False},
        effort_per_step={"inspect": "high", "summarize": "none", "repair": "low"},
    )
    assert pipeline.effort_for_step("inspect") == "high"
    assert pipeline.effort_for_step("summarize") == "none"
    assert pipeline.effort_for_step("diagnose") == "high"
    assert pipeline.effort_for_step("repair", attempt_index=2) == "low"


def test_effort_escalation_repair_ladder() -> None:
    pipeline = DebugPipelineConfig()
    assert pipeline.effort_for_step("repair", attempt_index=0) == "none"
    assert pipeline.effort_for_step("repair", attempt_index=1) == "low"
    assert pipeline.effort_for_step("repair", attempt_index=2) == "medium"
    assert pipeline.effort_for_step("repair", attempt_index=9) == "medium"


def test_effort_escalation_fix_ladder() -> None:
    pipeline = DebugPipelineConfig()
    assert pipeline.effort_for_step("fix", attempt_index=0) == "none"
    assert pipeline.effort_for_step("fix", attempt_index=1) == "low"
    assert pipeline.effort_for_step("fix", attempt_index=3) == "low"


def test_prompt_options_escalate_repair_effort_on_retry() -> None:
    config = DebugPipelineConfig(
        models={
            "per_step": {
                "repair": "xiaomi/mimo-v2.5-pro",
            },
        },
    )
    first = prompt_options_for_write_step(config, step="repair", attempt_index=0)
    retry = prompt_options_for_write_step(config, step="repair", attempt_index=1)
    assert first["reasoning_effort"] is None
    assert retry["reasoning_effort"] == "low"


def test_effort_per_step_rejects_unknown_step_key() -> None:
    with pytest.raises(ValueError, match="unknown debug_pipeline.effort_per_step"):
        DebugPipelineConfig(effort_per_step={"not_a_step": "low"})


def test_fusion_plugin_payload_matches_openrouter_shape() -> None:
    analysis = (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
    )
    invocation = build_fusion_invocation(
        fusion_model=FUSION_OUTER_MODEL,
        judge_model="deepseek/deepseek-v4-pro",
        analysis_models=analysis,
    )
    assert invocation.model == "openrouter/fusion"
    plugins = invocation.plugins_payload()
    assert plugins is not None
    assert plugins[0]["id"] == "fusion"
    assert plugins[0]["model"] == "deepseek/deepseek-v4-pro"
    assert plugins[0]["analysis_models"] == list(analysis)


def test_round_one_recognise_is_single_model_when_min_is_one() -> None:
    config = DebugPipelineConfig(min_board_models=1)
    invocation = resolve_step_invocation(config, "recognise", outer_round=1)
    assert invocation.use_fusion is False
    assert invocation.model == DEFAULT_SINGLE_MODEL


def test_round_one_recognise_uses_fusion_when_min_is_two() -> None:
    config = DebugPipelineConfig()
    invocation = resolve_step_invocation(config, "recognise", outer_round=1)
    assert invocation.use_fusion is True
    assert invocation.model == FUSION_OUTER_MODEL
    assert invocation.analysis_models == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
    )


def test_round_two_recognise_uses_fusion_escalation() -> None:
    config = DebugPipelineConfig()
    invocation = resolve_step_invocation(config, "recognise", outer_round=2)
    assert invocation.use_fusion is True
    assert invocation.model == FUSION_OUTER_MODEL
    assert invocation.judge_model == DEFAULT_SINGLE_MODEL
    assert invocation.analysis_models == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
    )


def test_resolve_repair_single_slug() -> None:
    config = DebugPipelineConfig()
    invocation = resolve_step_invocation(config, "repair", outer_round=3)
    assert invocation.use_fusion is False
    assert invocation.model == DEFAULT_SINGLE_MODEL
    assert invocation.plugins_payload() is None


def test_all_non_fusion_steps_stay_single() -> None:
    config = DebugPipelineConfig()
    for step in ("inspect", "plan", "repair", "fix", "summarize"):
        invocation = resolve_step_invocation(config, step, outer_round=3)  # type: ignore[arg-type]
        assert invocation.model == DEFAULT_SINGLE_MODEL
        assert invocation.use_fusion is False


def test_per_step_model_assignment() -> None:
    config = DebugPipelineConfig(
        models={
            "single": "deepseek/deepseek-v4-pro",
            "per_step": {
                "repair": "xiaomi/mimo-v2.5-pro",
                "fix": "xiaomi/mimo-v2.5-pro",
            },
        },
    )
    assert config.model_for_step("repair") == "xiaomi/mimo-v2.5-pro"
    assert config.model_for_step("diagnose") == "deepseek/deepseek-v4-pro"
    repair = resolve_step_invocation(config, "repair")
    assert repair.model == "xiaomi/mimo-v2.5-pro"


def test_single_model_flag_ignores_per_step() -> None:
    config = DebugPipelineConfig(
        models={
            "single_model": True,
            "single": "deepseek/deepseek-v4-pro",
            "per_step": {
                "repair": "xiaomi/mimo-v2.5-pro",
                "fix": "xiaomi/mimo-v2.5-pro",
            },
        },
    )
    assert config.model_for_step("repair") == "deepseek/deepseek-v4-pro"
    assert config.model_for_step("fix") == "deepseek/deepseek-v4-pro"
    assert resolve_step_invocation(config, "repair").model == "deepseek/deepseek-v4-pro"


def test_single_model_flag_still_allows_board_overrides() -> None:
    config = DebugPipelineConfig(
        models={
            "single_model": True,
            "single": "deepseek/deepseek-v4-pro",
            "per_step": {"recognise": "xiaomi/mimo-v2.5-pro"},
            "board_overrides": {
                "screen": {"recognise": "qwen/qwen3-vl-235b-a22b-thinking"},
            },
        },
    )
    assert config.model_for_step("recognise", board="forensic") == "deepseek/deepseek-v4-pro"
    assert config.model_for_step("recognise", board="screen") == (
        "qwen/qwen3-vl-235b-a22b-thinking"
    )


def test_board_override_takes_precedence_over_per_step() -> None:
    config = DebugPipelineConfig(
        models={
            "single": "deepseek/deepseek-v4-pro",
            "per_step": {"recognise": "deepseek/deepseek-v4-pro"},
            "board_overrides": {
                "screen": {"recognise": "qwen/qwen3-vl-235b-a22b-thinking"},
            },
        },
    )
    assert config.model_for_step("recognise", board="forensic") == ("deepseek/deepseek-v4-pro")
    assert config.model_for_step("recognise", board="screen") == (
        "qwen/qwen3-vl-235b-a22b-thinking"
    )
    screen = resolve_step_invocation(config, "recognise", board="screen", outer_round=1)
    assert screen.use_fusion is True
    assert screen.judge_model == "qwen/qwen3-vl-235b-a22b-thinking"
    assert screen.analysis_models[0] == "qwen/qwen3-vl-235b-a22b-thinking"


def test_per_step_rejects_unknown_step_key() -> None:
    with pytest.raises(ValueError, match="unknown debug_pipeline.models.per_step"):
        DebugPipelineModelsConfig(per_step={"not_a_step": "vendor/model"})


def test_fusion_rejects_more_than_eight_panelists() -> None:
    models = tuple(f"provider/model-{index}" for index in range(9))
    with pytest.raises(ValueError, match="at most 8"):
        build_fusion_invocation(
            fusion_model=FUSION_OUTER_MODEL,
            judge_model="deepseek/deepseek-v4-pro",
            analysis_models=models,
        )


def test_yaml_debug_pipeline_override(tmp_path) -> None:
    yaml_path = tmp_path / ".ai-figma-flutter.yml"
    yaml_path.write_text(
        """
debug_pipeline:
  effort: low
  models:
    single: custom/vendor-model
""",
        encoding="utf-8",
    )
    settings = load_settings(yaml_path)
    assert settings.agent.debug_pipeline.effort == "low"
    assert settings.agent.debug_pipeline.models.single == "custom/vendor-model"
