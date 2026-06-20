"""Tests for debug_pipeline model policy and OpenRouter Fusion payloads."""

from __future__ import annotations

import pytest

from figma_flutter_agent.config import AgentYamlConfig, load_settings
from figma_flutter_agent.config.debug_pipeline import (
    DEFAULT_DIAGNOSE_PANEL,
    DEFAULT_RECOGNISE_PANEL,
    DEFAULT_REVIEW_PANEL,
    DEFAULT_SINGLE_MODEL,
    FUSION_JUDGE_MODEL,
    FUSION_OUTER_MODEL,
    DebugPipelineConfig,
)
from figma_flutter_agent.dev.opencode.model_policy import resolve_step_invocation
from figma_flutter_agent.llm.openrouter_fusion import (
    build_fusion_invocation,
    build_single_invocation,
)


def test_debug_pipeline_defaults_embedded_in_agent_yaml() -> None:
    agent = AgentYamlConfig()
    pipeline = agent.debug_pipeline
    assert pipeline.effort == "high"
    assert pipeline.reasoning_settings().effort == "high"
    assert pipeline.openrouter.fusion_model == FUSION_OUTER_MODEL
    assert pipeline.openrouter.judge_model == FUSION_JUDGE_MODEL
    assert pipeline.panels.recognise == DEFAULT_RECOGNISE_PANEL
    assert pipeline.panels.diagnose == DEFAULT_DIAGNOSE_PANEL
    assert pipeline.panels.review == DEFAULT_REVIEW_PANEL
    assert pipeline.models.single == DEFAULT_SINGLE_MODEL
    assert pipeline.openrouter.judge_model == pipeline.models.single


def test_fusion_plugin_payload_matches_openrouter_shape() -> None:
    invocation = build_fusion_invocation(
        fusion_model=FUSION_OUTER_MODEL,
        judge_model=FUSION_JUDGE_MODEL,
        analysis_models=DEFAULT_RECOGNISE_PANEL,
    )
    assert invocation.model == "openrouter/fusion"
    plugins = invocation.plugins_payload()
    assert plugins is not None
    assert plugins[0]["id"] == "fusion"
    assert plugins[0]["model"] == FUSION_JUDGE_MODEL
    assert plugins[0]["analysis_models"] == list(DEFAULT_RECOGNISE_PANEL)
    assert "qwen/qwen3-vl-235b-a22b-thinking" in plugins[0]["analysis_models"]


def test_diagnose_panel_uses_qwen_max_not_vl() -> None:
    config = DebugPipelineConfig()
    panel = config.panel_for_step("diagnose")
    assert panel[0] == "qwen/qwen3.7-max"
    assert "qwen/qwen3-vl-235b-a22b-thinking" not in panel


def test_resolve_recognise_fusion_when_ensemble_enabled() -> None:
    config = DebugPipelineConfig()
    invocation = resolve_step_invocation(config, "recognise")
    assert invocation.use_fusion is True
    assert invocation.model == FUSION_OUTER_MODEL
    assert invocation.judge_model == FUSION_JUDGE_MODEL


def test_resolve_repair_single_slug() -> None:
    config = DebugPipelineConfig()
    invocation = resolve_step_invocation(config, "repair")
    assert invocation.use_fusion is False
    assert invocation.model == DEFAULT_SINGLE_MODEL
    assert invocation.plugins_payload() is None


def test_all_single_steps_use_same_slug() -> None:
    config = DebugPipelineConfig()
    for step in ("inspect", "plan", "repair", "fix", "summarize"):
        invocation = resolve_step_invocation(config, step)  # type: ignore[arg-type]
        assert invocation.model == DEFAULT_SINGLE_MODEL
        assert invocation.use_fusion is False


def test_ensemble_off_uses_single_fallback() -> None:
    config = DebugPipelineConfig(ensemble={"enabled": False})
    invocation = resolve_step_invocation(config, "diagnose")
    assert invocation == build_single_invocation(model=DEFAULT_SINGLE_MODEL)


def test_fusion_rejects_more_than_eight_panelists() -> None:
    models = tuple(f"provider/model-{index}" for index in range(9))
    with pytest.raises(ValueError, match="at most 8"):
        build_fusion_invocation(
            fusion_model=FUSION_OUTER_MODEL,
            judge_model=FUSION_JUDGE_MODEL,
            analysis_models=models,
        )


def test_yaml_debug_pipeline_override(tmp_path) -> None:
    yaml_path = tmp_path / ".ai-figma-flutter.yml"
    yaml_path.write_text(
        """
debug_pipeline:
  effort: low
  ensemble:
    enabled: false
  models:
    single: custom/vendor-model
""",
        encoding="utf-8",
    )
    settings = load_settings(yaml_path)
    assert settings.agent.debug_pipeline.effort == "low"
    assert settings.agent.debug_pipeline.ensemble.enabled is False
    assert settings.agent.debug_pipeline.models.single == "custom/vendor-model"
