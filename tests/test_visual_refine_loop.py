"""Tests for iterative LLM visual refine loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.generator.validation import PlannedAnalyzeOutcome
from figma_flutter_agent.llm.prompts import build_visual_refine_system_prompt
from figma_flutter_agent.llm.repair import build_visual_refine_user_payload
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
)
from figma_flutter_agent.stages.llm import LlmStageResult
from figma_flutter_agent.stages.llm_repair import LlmRepairStageRequest
from figma_flutter_agent.stages.visual_refine import run_visual_refine_loop
from figma_flutter_agent.validation.golden_capture import GoldenCaptureResult
from figma_flutter_agent.validation.pixeldiff import PixelDiffResult


def _settings(**generation_overrides: Any) -> Settings:
    return Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
        agent=AgentYamlConfig(
            generation=GenerationConfig(
                use_deterministic_screen=False,
                llm_visual_refine=True,
                llm_visual_refine_max_attempts=2,
                llm_visual_refine_threshold=0.08,
                llm_visual_refine_capture_golden=True,
                **generation_overrides,
            ),
            validation={"generate_golden_test": True},
        ),
    )


def _request(**overrides: Any) -> LlmRepairStageRequest:
    base = LlmRepairStageRequest(
        settings=_settings(),
        dry_run=False,
        project_dir=Path("."),
        planned_files={"test/golden/demo_screen_test.dart": "// test"},
        llm_result=LlmStageResult(
            generation=FlutterGenerationResponse(screen_code="class DemoScreen {}"),
        ),
        use_deterministic_screen=False,
        clean_tree=CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.CONTAINER),
        tokens=DesignTokens(),
        resolved_feature="demo",
        node_id="1:1",
        cluster_summary={},
        asset_manifest=MagicMock(entries=[]),
        font_manifest=MagicMock(),
        widget_hints=[],
        navigation_hints=[],
        routing_on=False,
        navigation_plan=MagicMock(),
        figma_root={},
        package_name="demo_app",
        figma_reference_png=b"\x89PNG\r\n\x1a\nfigma",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_build_visual_refine_system_prompt_includes_mode() -> None:
    prompt = build_visual_refine_system_prompt()
    stack_prompt = build_visual_refine_system_prompt(stack_root=True)
    assert "Visual Delta Feedback" in prompt
    assert "IMAGE 3" in prompt
    assert "TRIPLE COMPARISON MANDATE" in prompt
    assert "figma_reference" in prompt
    assert "flutter_render" in prompt
    assert "visual_diff_heatmap" in prompt
    assert "NEVER SWAP THEIR ROLES" in prompt
    assert "STACK ROOT LAYOUT" in stack_prompt
    assert "<Thinking>" not in prompt


def test_build_visual_refine_user_payload_includes_visual_diff() -> None:
    generation = FlutterGenerationResponse(screen_code="class DemoScreen {}")
    payload_text = build_visual_refine_user_payload(
        feature_name="demo",
        clean_tree=CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.CONTAINER),
        tokens=DesignTokens(),
        asset_manifest=[],
        current_generation=generation,
        changed_ratio=0.12,
        threshold=0.08,
    )
    from figma_flutter_agent.llm.payload_format import parse_labeled_user_payload

    assert "### mode" in payload_text
    assert "### visualDiff" in payload_text
    payload = parse_labeled_user_payload(payload_text)
    assert payload["mode"] == "visual_refine"
    assert payload["visualDiff"]["changedRatio"] == 0.12
    assert len(payload["attachedImages"]) == 3
    assert payload["attachedImages"][2]["role"] == "visual_diff_heatmap"


@pytest.mark.asyncio
async def test_visual_refine_loop_skips_when_diff_already_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.stages.visual_refine.capture_planned_flutter_golden_png",
        lambda *_args, **_kwargs: GoldenCaptureResult(png=b"\x89PNG\r\n\x1a\nflutter"),
    )
    monkeypatch.setattr(
        "figma_flutter_agent.stages.visual_refine.compare_png_bytes",
        lambda *_args, **_kwargs: PixelDiffResult(
            reference_path="a",
            actual_path="b",
            width=1,
            height=1,
            changed_pixels=0,
            total_pixels=1,
            changed_ratio=0.03,
            threshold=0.08,
        ),
    )
    factory = MagicMock()

    result = await run_visual_refine_loop(
        _request(),
        planned_files={"test/golden/demo_screen_test.dart": "// test"},
        llm_client_factory=factory,
    )

    factory.assert_not_called()
    assert result.refine_attempts == 0
    assert result.final_changed_ratio == 0.03


@pytest.mark.asyncio
async def test_visual_refine_loop_refines_until_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ratios = [0.15, 0.04]

    monkeypatch.setattr(
        "figma_flutter_agent.stages.visual_refine.capture_planned_flutter_golden_png",
        lambda *_args, **_kwargs: GoldenCaptureResult(png=b"\x89PNG\r\n\x1a\nflutter"),
    )

    def fake_compare(*_args, **_kwargs) -> PixelDiffResult:
        ratio = ratios.pop(0)
        return PixelDiffResult(
            reference_path="a",
            actual_path="b",
            width=1,
            height=1,
            changed_pixels=int(ratio * 100),
            total_pixels=100,
            changed_ratio=ratio,
            threshold=0.08,
        )

    monkeypatch.setattr(
        "figma_flutter_agent.stages.visual_refine.compare_png_bytes",
        fake_compare,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.stages.visual_refine.analyze_planned_dart_files",
        lambda *_args, **_kwargs: PlannedAnalyzeOutcome(
            skipped=False,
            passed=True,
            detail="ok",
        ),
    )

    refined = FlutterGenerationResponse(screen_code="class RefinedScreen {}")
    mock_client = MagicMock()
    mock_client.visual_refine_async = AsyncMock(return_value=refined)

    replanned = {"test/golden/demo_screen_test.dart": "// refined"}

    monkeypatch.setattr(
        "figma_flutter_agent.stages.visual_refine.replan_planned_files",
        lambda *_args, **_kwargs: replanned,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.stages.visual_refine.render_visual_diff_heatmap_png",
        lambda *_args, **_kwargs: b"\x89PNG\r\n\x1a\ndiff",
    )

    result = await run_visual_refine_loop(
        _request(),
        planned_files={"test/golden/demo_screen_test.dart": "// test"},
        llm_client_factory=lambda _settings: mock_client,
    )

    mock_client.visual_refine_async.assert_awaited_once()
    refine_kwargs = mock_client.visual_refine_async.await_args.kwargs
    assert refine_kwargs["refine_attempt"] == 1
    assert refine_kwargs["visual_diff_png"] == b"\x89PNG\r\n\x1a\ndiff"
    assert refine_kwargs["refine_focus"] == "interaction"
    assert refine_kwargs["interactive_inventory"] is not None
    assert refine_kwargs["handler_audit"] is not None
    assert result.refine_attempts == 1
    assert result.initial_changed_ratio == 0.15
    assert result.final_changed_ratio == 0.04
    assert result.planned_files == replanned
