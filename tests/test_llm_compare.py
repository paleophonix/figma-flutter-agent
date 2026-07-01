"""Tests for wizard multi-model IR compare."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.paths import compare_ir_artifact_path
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.compare import write_compare_ir_artifact
from figma_flutter_agent.schemas import (
    ExtractedWidget,
    FlutterGenerationResponse,
    ScreenIr,
    WidgetIrNode,
)


def test_resolved_llm_compare_models_requires_three_slots() -> None:
    settings = Settings(
        LLM_PROVIDER="openrouter",
        OPENROUTER_API_KEY="test-key",
        LLM_GENERATE_MODEL="model-a",
        LLM_GENERATE_MODEL_2="model-b",
        LLM_GENERATE_MODEL_3="model-c",
    )
    assert settings.resolved_llm_compare_models() == ["model-a", "model-b", "model-c"]


def test_resolved_llm_compare_models_raises_when_slot_missing() -> None:
    settings = Settings(
        LLM_PROVIDER="openrouter",
        OPENROUTER_API_KEY="test-key",
        LLM_GENERATE_MODEL="model-a",
    )
    with pytest.raises(LlmError, match="LLM_GENERATE_MODEL_2"):
        settings.resolved_llm_compare_models()


def test_write_compare_ir_artifact(tmp_path: Path) -> None:
    response = FlutterGenerationResponse(
        screenIr=ScreenIr(root=WidgetIrNode(figmaId="1:2")),
        extractedWidgets=[
            ExtractedWidget(widgetName="DemoWidget", widgetIr=WidgetIrNode(figmaId="1:3"))
        ],
    )
    path = write_compare_ir_artifact(
        project_dir=tmp_path,
        feature_name="login",
        index=2,
        model="z-ai/glm-5.2",
        response=response,
    )
    assert path == compare_ir_artifact_path(tmp_path, "login", 2)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["stage"] == "compare"
    assert payload["index"] == 2
    assert payload["model"] == "z-ai/glm-5.2"
    assert payload["featureName"] == "login"
    assert payload["screenIr"]["root"]["figmaId"] == "1:2"
    assert payload["extractedWidgets"][0]["widgetName"] == "DemoWidget"
