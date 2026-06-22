"""Tests for round-based Fusion escalation."""

from __future__ import annotations

import pytest

from figma_flutter_agent.config.debug_pipeline import (
    DEFAULT_BOARD_MODELS,
    FUSION_OUTER_MODEL,
    DebugPipelineConfig,
)
from figma_flutter_agent.dev.opencode.fusion_escalation import build_escalation_panel
from figma_flutter_agent.dev.opencode.model_policy import resolve_step_invocation


def test_escalation_panel_round_one_with_default_min() -> None:
    panel = build_escalation_panel(
        "deepseek/deepseek-v4-pro",
        DEFAULT_BOARD_MODELS,
        1,
        min_panel_size=2,
        max_panel_size=4,
    )
    assert panel == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
    )


def test_escalation_panel_round_one_with_min_three() -> None:
    panel = build_escalation_panel(
        "deepseek/deepseek-v4-pro",
        DEFAULT_BOARD_MODELS,
        1,
        min_panel_size=3,
        max_panel_size=4,
    )
    assert panel == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
        "minimax/minimax-m3",
    )


def test_escalation_panel_round_two_base_plus_first_distinct() -> None:
    panel = build_escalation_panel(
        "deepseek/deepseek-v4-pro",
        DEFAULT_BOARD_MODELS,
        2,
    )
    assert panel == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
    )


def test_escalation_panel_grows_each_round_up_to_four() -> None:
    base = "deepseek/deepseek-v4-pro"
    assert len(build_escalation_panel(base, DEFAULT_BOARD_MODELS, 3)) == 3
    assert len(build_escalation_panel(base, DEFAULT_BOARD_MODELS, 4)) == 4
    assert build_escalation_panel(base, DEFAULT_BOARD_MODELS, 5) == build_escalation_panel(
        base,
        DEFAULT_BOARD_MODELS,
        4,
    )


def test_escalation_panel_respects_max_board_models() -> None:
    panel = build_escalation_panel(
        "deepseek/deepseek-v4-pro",
        DEFAULT_BOARD_MODELS,
        5,
        min_panel_size=2,
        max_panel_size=3,
    )
    assert panel == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
        "minimax/minimax-m3",
    )


def test_escalation_panel_rejects_fusion_disabled_min() -> None:
    with pytest.raises(ValueError, match="min_panel_size>=2"):
        build_escalation_panel(
            "deepseek/deepseek-v4-pro",
            DEFAULT_BOARD_MODELS,
            1,
            min_panel_size=1,
        )


def test_debug_pipeline_rejects_min_above_max_board_models() -> None:
    with pytest.raises(ValueError, match="min_board_models must be <= max_board_models"):
        DebugPipelineConfig(min_board_models=5, max_board_models=3)


def test_escalation_panel_non_base_step_model() -> None:
    panel = build_escalation_panel(
        "qwen/qwen3-vl-235b-a22b-thinking",
        DEFAULT_BOARD_MODELS,
        2,
    )
    assert panel == (
        "qwen/qwen3-vl-235b-a22b-thinking",
        "deepseek/deepseek-v4-pro",
    )


def test_min_board_models_one_uses_base_model_only() -> None:
    config = DebugPipelineConfig(min_board_models=1)
    invocation = resolve_step_invocation(config, "diagnose", outer_round=1)
    assert invocation.use_fusion is False
    assert invocation.model == "deepseek/deepseek-v4-pro"


def test_min_board_models_three_fusion_on_round_one() -> None:
    config = DebugPipelineConfig(
        board_models=DEFAULT_BOARD_MODELS,
        min_board_models=3,
        max_board_models=4,
    )
    invocation = resolve_step_invocation(config, "diagnose", outer_round=1)
    assert invocation.use_fusion is True
    assert invocation.model == FUSION_OUTER_MODEL
    assert invocation.analysis_models == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
        "minimax/minimax-m3",
    )


def test_min_board_models_two_fusion_on_round_one() -> None:
    config = DebugPipelineConfig(board_models=DEFAULT_BOARD_MODELS, min_board_models=2)
    invocation = resolve_step_invocation(config, "recognise", outer_round=1)
    assert invocation.use_fusion is True
    assert invocation.analysis_models == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
    )


def test_round_two_fusion_escalation_judge_is_base() -> None:
    config = DebugPipelineConfig(
        board_models=DEFAULT_BOARD_MODELS,
        models={
            "single": "deepseek/deepseek-v4-pro",
            "per_step": {"diagnose": "deepseek/deepseek-v4-pro"},
        },
    )
    invocation = resolve_step_invocation(config, "diagnose", outer_round=2)
    assert invocation.use_fusion is True
    assert invocation.model == FUSION_OUTER_MODEL
    assert invocation.judge_model == "deepseek/deepseek-v4-pro"
    assert invocation.analysis_models == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
    )


def test_round_three_adds_third_board_model() -> None:
    config = DebugPipelineConfig(board_models=DEFAULT_BOARD_MODELS)
    invocation = resolve_step_invocation(config, "review", outer_round=3)
    assert invocation.analysis_models == (
        "deepseek/deepseek-v4-pro",
        "xiaomi/mimo-v2.5-pro",
        "minimax/minimax-m3",
    )


def test_inspect_never_uses_fusion() -> None:
    config = DebugPipelineConfig()
    invocation = resolve_step_invocation(config, "inspect", outer_round=3)
    assert invocation.use_fusion is False


def test_empty_board_models_disables_fusion() -> None:
    config = DebugPipelineConfig(board_models=())
    invocation = resolve_step_invocation(config, "diagnose", outer_round=3)
    assert invocation.use_fusion is False


def test_fusion_escalation_flag_disables_panel() -> None:
    config = DebugPipelineConfig(
        board_models=DEFAULT_BOARD_MODELS,
        fusion_escalation=False,
    )
    invocation = resolve_step_invocation(config, "diagnose", outer_round=3)
    assert invocation.use_fusion is False
    assert invocation.model == "deepseek/deepseek-v4-pro"
