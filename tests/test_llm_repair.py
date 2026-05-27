"""Tests for LLM analyze repair loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.generator.validation import PlannedAnalyzeOutcome
from figma_flutter_agent.llm.prompts import build_repair_system_prompt
from figma_flutter_agent.llm.repair import build_repair_user_payload
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
)
from figma_flutter_agent.stages.llm import LlmStageResult
from figma_flutter_agent.stages.llm_repair import LlmRepairStageRequest, run_analyze_repair_loop


def _settings(**generation_overrides: Any) -> Settings:
    return Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
        agent=AgentYamlConfig(
            generation=GenerationConfig(
                use_deterministic_screen=False,
                llm_repair_after_analyze=True,
                llm_repair_max_attempts=2,
                **generation_overrides,
            ),
        ),
    )


def _repair_request(**overrides: Any) -> LlmRepairStageRequest:
    base = LlmRepairStageRequest(
        settings=_settings(),
        dry_run=False,
        project_dir=Path("."),
        planned_files={"lib/features/demo/demo_screen.dart": "class Bad {}"},
        llm_result=LlmStageResult(
            generation=FlutterGenerationResponse(screen_code="class BadScreen {}"),
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
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_build_repair_system_prompt_includes_repair_mode() -> None:
    prompt = build_repair_system_prompt()
    assert "REPAIR PATCH MODE" in prompt
    assert "repairTargets" in prompt or "unchangedWidgetNames" in prompt


def test_build_repair_user_payload_includes_scoped_targets() -> None:
    from figma_flutter_agent.llm.repair_scope import RepairScope, RepairTarget

    generation = FlutterGenerationResponse(
        screen_code="class DemoScreen {}",
        extracted_widgets=[],
    )
    scope = RepairScope(
        targets=(
            RepairTarget(
                target="screenCode",
                widget_name=None,
                code=generation.screen_code,
                planned_path="lib/features/demo/demo_screen.dart",
                errors=("error - lib/features/demo/demo_screen.dart:1:1 - undefined_identifier",),
                planned_excerpt="   1| class DemoScreen {}",
            ),
        )
    )
    payload = json.loads(
        build_repair_user_payload(
            feature_name="demo",
            scope=scope,
            analyze_errors=["error - lib/features/demo/demo_screen.dart:1:1 - undefined_identifier"],
        )
    )
    assert payload["mode"] == "repair_patch"
    assert payload["repairTargets"][0]["code"] == generation.screen_code
    assert payload["analyzeErrors"] == [
        "error - lib/features/demo/demo_screen.dart:1:1 - undefined_identifier"
    ]


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_skips_when_deterministic() -> None:
    factory = MagicMock()
    result = await run_analyze_repair_loop(
        _repair_request(
            use_deterministic_screen=True,
            llm_client_factory=factory,
        )
    )

    factory.assert_not_called()
    assert result.repair_attempts == 0


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_continues_on_repeated_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    same_error = (
        "line 15, column 3 of c:/Temp/figma-flutter-spec23-aaa/analyze_check/lib/widgets/group_widget.dart: "
        "Getters, setters and methods can't be declared to be 'const'."
    )
    analyze_outcomes = [
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="dart analyze failed",
            errors=(same_error,),
        ),
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="dart analyze failed",
            errors=(
                "line 15, column 3 of c:/Temp/figma-flutter-spec23-bbb/analyze_check/lib/widgets/group_widget.dart: "
                "Getters, setters and methods can't be declared to be 'const'.",
            ),
        ),
    ]
    call_count = 0

    def fake_analyze(*_args: object, **_kwargs: object) -> PlannedAnalyzeOutcome:
        nonlocal call_count
        call_count += 1
        return analyze_outcomes.pop(0) if analyze_outcomes else PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="dart analyze failed",
            errors=(same_error,),
        )

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.analyze_planned_dart_files",
        fake_analyze,
    )
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock(
        return_value=FlutterGenerationResponse(screen_code="class StillBad {}"),
    )

    settings = _settings()
    settings.agent.generation.llm_repair_max_attempts = 2
    result = await run_analyze_repair_loop(
        _repair_request(
            llm_client_factory=lambda _s: mock_client,
            settings=settings,
        )
    )

    assert mock_client.repair_async.await_count == 2
    assert result.repair_attempts == 2
    assert not any("repeated identical analyzer errors" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_keeps_trying_on_dart_format_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parse_error = (
        "line 147, column 31 of c:/Temp/figma-flutter-spec23-aaa/analyze_check/lib/features/demo/demo_screen.dart: "
        "Expected to find ']'."
    )
    analyze_outcomes = [
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="dart format failed for generated project",
            errors=(parse_error,),
        ),
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="dart format failed for generated project",
            errors=(parse_error,),
        ),
        PlannedAnalyzeOutcome(skipped=False, passed=True, detail="dart analyze passed"),
    ]

    def fake_analyze(*_args: object, **_kwargs: object) -> PlannedAnalyzeOutcome:
        return analyze_outcomes.pop(0)

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.analyze_planned_dart_files",
        fake_analyze,
    )
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock(
        return_value=FlutterGenerationResponse(screen_code="class FixedScreen {}"),
    )

    settings = _settings()
    settings.agent.generation.llm_repair_max_attempts = 5
    result = await run_analyze_repair_loop(
        _repair_request(
            llm_client_factory=lambda _s: mock_client,
            settings=settings,
        )
    )

    assert mock_client.repair_async.await_count == 2
    assert result.repair_attempts == 2
    assert not any("repeated identical analyzer errors" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_repairs_and_replans(monkeypatch: pytest.MonkeyPatch) -> None:
    analyze_outcomes = [
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="dart analyze failed",
            errors=("error - lib/demo.dart:1:1 - undefined_identifier",),
        ),
        PlannedAnalyzeOutcome(skipped=False, passed=True, detail="dart analyze passed"),
    ]

    def fake_analyze(*_args: object, **_kwargs: object) -> PlannedAnalyzeOutcome:
        return analyze_outcomes.pop(0)

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.analyze_planned_dart_files",
        fake_analyze,
    )

    fixed_generation = FlutterGenerationResponse(screen_code="class FixedScreen {}")
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock(return_value=fixed_generation)

    replanned = {"lib/features/demo/demo_screen.dart": "class Fixed {}"}

    def fake_plan(_request: object) -> MagicMock:
        return MagicMock(planned_files=replanned)

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.plan_generation_output",
        fake_plan,
    )

    result = await run_analyze_repair_loop(
        _repair_request(llm_client_factory=lambda _settings: mock_client)
    )

    mock_client.repair_async.assert_awaited_once()
    assert result.repair_attempts == 1
    assert result.planned_files == replanned
    assert result.llm_result.generation == fixed_generation
