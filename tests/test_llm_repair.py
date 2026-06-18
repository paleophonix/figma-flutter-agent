"""Tests for LLM analyze repair loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.errors import GenerationError, LlmRepairStalledError
from figma_flutter_agent.generator.dart.project_validation import PlannedAnalyzeOutcome
from figma_flutter_agent.llm.prompts import build_repair_system_prompt
from figma_flutter_agent.llm.repair import build_repair_user_payload
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    FlutterGenerationResponse,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)
from figma_flutter_agent.stages.llm import LlmStageResult
from figma_flutter_agent.stages.llm_repair import (
    CRITICAL_SYNTAX_BROKEN_TAG,
    LlmRepairStageRequest,
    LlmRepairStageResult,
    _apply_extracted_widget_reference_fixup,
    _format_failure_paths_from_outcome,
    _repair_patch_has_duplicate_required_this,
    _syntax_repair_stalled,
    run_analyze_repair_loop,
)


def _settings(**generation_overrides: Any) -> Settings:
    return Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
        agent=AgentYamlConfig(
            generation=GenerationConfig(
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


def test_syntax_repair_stalled_detects_non_decreasing_counts() -> None:
    assert _syntax_repair_stalled([5, 5, 5], 2)
    assert _syntax_repair_stalled([5, 5, 6], 2)
    assert not _syntax_repair_stalled([6, 5, 4], 2)


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_raises_on_syntax_stall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parse_error = "line 10, column 1 of lib/widgets/custom_input_field.dart: Expected to find ']'."
    failing = PlannedAnalyzeOutcome(
        skipped=False,
        passed=False,
        detail="dart format failed for generated project",
        errors=(parse_error,),
        format_failed_paths=("lib/widgets/custom_input_field.dart",),
    )

    def fake_analyze(*_args: object, **_kwargs: object) -> PlannedAnalyzeOutcome:
        return failing

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.analyze_planned_dart_files",
        fake_analyze,
    )
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock(
        return_value=FlutterGenerationResponse(
            screen_code="class StillBrokenScreen extends StatefulWidget {\n"
            "  @override\n"
            "  State<StillBrokenScreen> createState() => _StillBrokenScreenState();\n"
            "}\n"
            "class _StillBrokenScreenState extends State<StillBrokenScreen> {\n"
            "  @override\n"
            "  Widget build(BuildContext context) => const SizedBox();\n"
            "}\n"
        ),
    )
    base_settings = _settings()
    settings = base_settings.model_copy(
        update={
            "agent": base_settings.agent.model_copy(
                update={
                    "generation": base_settings.agent.generation.model_copy(
                        update={
                            "llm_repair_max_attempts": 4,
                            "llm_repair_syntax_stall_limit": 2,
                            "llm_repair_cpi_supervisor": False,
                        }
                    )
                }
            )
        }
    )
    with pytest.raises(LlmRepairStalledError, match="stalled"):
        await run_analyze_repair_loop(
            _repair_request(
                llm_client_factory=lambda _s: mock_client,
                settings=settings,
            )
        )


def test_build_repair_system_prompt_includes_apr_layers() -> None:
    prompt = build_repair_system_prompt()
    assert "<L1:PURPOSE>" in prompt
    assert "<L6:ENVIRONMENT>" in prompt
    assert "FlutterRepairPatchResponse" in prompt
    assert "EXTRACTED WIDGET IDENTIFIER SYNC" in build_repair_system_prompt()


def test_apply_extracted_widget_reference_fixup_rewrites_private_usages() -> None:
    background = """class _AmbientBackground extends StatelessWidget {
  const _AmbientBackground({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    screen = """class SignInScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) => const _AmbientBackground();
}
"""
    generation = FlutterGenerationResponse(
        screen_code=screen,
        extracted_widgets=[
            ExtractedWidget(widget_name="ambientbackground", code=background),
        ],
    )
    request = _repair_request(
        llm_result=LlmStageResult(generation=generation),
        resolved_feature="sign_in",
    )
    result = LlmRepairStageResult(
        planned_files=dict(request.planned_files),
        llm_result=request.llm_result,
    )
    assert _apply_extracted_widget_reference_fixup(request, result, log=MagicMock()) is True
    assert "_AmbientBackground" not in generation.screen_code
    assert "AmbientBackground(" in generation.screen_code


def test_apply_extracted_widget_reference_fixup_ir_mode_reconciles_layout() -> None:
    widget = """import 'package:flutter/material.dart';

class _Group17Widget extends StatelessWidget {
  const _Group17Widget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    layout = """import 'package:flutter/material.dart';

class SignUpAndSignInLayout extends StatelessWidget {
  const SignUpAndSignInLayout({super.key});
  @override
  Widget build(BuildContext context) => const _Group17Widget();
}
"""
    generation = FlutterGenerationResponse(
        screen_code=None,
        screen_ir=ScreenIr(
            root=WidgetIrNode(figma_id="1:1", kind=WidgetIrKind.STACK, children=[]),
        ),
        extracted_widgets=[
            ExtractedWidget(widget_name="group17widget", code=widget),
        ],
    )
    planned = {
        "lib/generated/sign_up_and_sign_in_layout.dart": layout,
        "lib/widgets/group17_widget.dart": widget,
    }
    request = _repair_request(
        llm_result=LlmStageResult(generation=generation),
        resolved_feature="sign_up_and_sign_in",
        planned_files=planned,
    )
    result = LlmRepairStageResult(
        planned_files=dict(planned),
        llm_result=request.llm_result,
    )
    assert _apply_extracted_widget_reference_fixup(request, result, log=MagicMock()) is True
    layout_out = result.planned_files["lib/generated/sign_up_and_sign_in_layout.dart"]
    assert "_Group17Widget" not in layout_out
    assert "Group17Widget(" in layout_out


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
    from figma_flutter_agent.llm.payload_format import parse_labeled_user_payload

    payload = parse_labeled_user_payload(
        build_repair_user_payload(
            feature_name="demo",
            scope=scope,
            analyze_errors=[
                "error - lib/features/demo/demo_screen.dart:1:1 - undefined_identifier"
            ],
        )
    )
    assert payload["mode"] == "repair_patch"
    assert payload["repairTargets"][0]["code"] == generation.screen_code
    assert payload["analyzeErrors"] == [
        "error - lib/features/demo/demo_screen.dart:1:1 - undefined_identifier"
    ]


@pytest.mark.asyncio
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
        return (
            analyze_outcomes.pop(0)
            if analyze_outcomes
            else PlannedAnalyzeOutcome(
                skipped=False,
                passed=False,
                detail="dart analyze failed",
                errors=(same_error,),
            )
        )

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.analyze_planned_dart_files",
        fake_analyze,
    )
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock(
        return_value=FlutterGenerationResponse(screen_code="class StillBad {}"),
    )

    base_settings = _settings()
    settings = base_settings.model_copy(
        update={
            "agent": base_settings.agent.model_copy(
                update={
                    "generation": base_settings.agent.generation.model_copy(
                        update={
                            "llm_repair_max_attempts": 2,
                            "llm_repair_cpi_supervisor": False,
                        }
                    )
                }
            )
        }
    )
    result = await run_analyze_repair_loop(
        _repair_request(
            llm_client_factory=lambda _s: mock_client,
            settings=settings,
        )
    )

    assert mock_client.repair_async.await_count >= 2
    assert result.repair_attempts >= 1
    assert not any("repeated identical analyzer errors" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_rolls_back_and_escalates_on_format_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    screen_path = "lib/features/sign_in/sign_in_screen.dart"
    pre_reconcile = "class SignInScreen extends StatelessWidget { const SignInScreen(); }"
    parse_error = (
        f"line 77, column 950 of C:/Temp/analyze_check/{screen_path}: Expected to find ','."
    )
    analyze_outcomes = [
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="dart format failed for generated project",
            errors=(parse_error,),
            format_failed_paths=(screen_path,),
        ),
        PlannedAnalyzeOutcome(skipped=False, passed=True, detail="dart analyze passed"),
    ]

    def fake_analyze(*_args: object, **_kwargs: object) -> PlannedAnalyzeOutcome:
        return analyze_outcomes.pop(0)

    reconcile_calls = {"count": 0}

    def fake_reconcile(planned: dict[str, str], **_: object) -> dict[str, str]:
        reconcile_calls["count"] += 1
        updated = dict(planned)
        if reconcile_calls["count"] == 1:
            updated[screen_path] = pre_reconcile + "\n}}}}"
        return updated

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.analyze_planned_dart_files",
        fake_analyze,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.reconcile_planned_dart_files",
        fake_reconcile,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.repair_planned_format_parse_failures",
        lambda planned, _paths, **_: dict(planned),
    )
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock(
        return_value=FlutterGenerationResponse(screen_code="class FixedScreen {}"),
    )
    mock_client.cpi_supervisor_async = AsyncMock(
        return_value=MagicMock(
            pattern_interrupt_directive="REWRITE THE SCREEN FILE COMPLETELY.",
            analysis="Format parse failure detected.",
        ),
    )

    settings = _settings()
    settings.agent.generation.llm_repair_max_attempts = 3
    settings.agent.generation.llm_repair_cpi_supervisor = True
    request = _repair_request(
        llm_client_factory=lambda _s: mock_client,
        settings=settings,
    )
    request.planned_files[screen_path] = pre_reconcile

    result = await run_analyze_repair_loop(request)

    mock_client.repair_async.assert_awaited_once()
    mock_client.cpi_supervisor_async.assert_awaited()
    cpi_errors = mock_client.cpi_supervisor_async.await_args.kwargs["analyze_errors"]
    assert any(CRITICAL_SYNTAX_BROKEN_TAG in item for item in cpi_errors)
    assert result.repair_attempts == 1


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_keeps_trying_on_dart_format_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parse_error = (
        "line 147, column 31 of c:/Temp/figma-flutter-spec23-aaa/analyze_check/lib/features/demo/demo_screen.dart: "
        "Expected to find ']'."
    )
    demo_path = "lib/features/demo/demo_screen.dart"
    analyze_outcomes = [
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="dart format failed for generated project",
            errors=(parse_error,),
            format_failed_paths=(demo_path,),
        ),
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="dart format failed for generated project",
            errors=(parse_error,),
            format_failed_paths=(demo_path,),
        ),
        PlannedAnalyzeOutcome(skipped=False, passed=True, detail="dart analyze passed"),
    ]

    def fake_analyze(*_args: object, **_kwargs: object) -> PlannedAnalyzeOutcome:
        return analyze_outcomes.pop(0)

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.analyze_planned_dart_files",
        fake_analyze,
    )
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock(
        return_value=FlutterGenerationResponse(screen_code="class FixedScreen {}"),
    )
    mock_client.cpi_supervisor_async = AsyncMock(
        return_value=MagicMock(
            pattern_interrupt_directive="REWRITE UNPARSEABLE FILES.",
            analysis="dart format could not parse sources.",
        ),
    )

    settings = _settings()
    settings.agent.generation.llm_repair_max_attempts = 5
    settings.agent.generation.llm_repair_cpi_supervisor = True
    result = await run_analyze_repair_loop(
        _repair_request(
            llm_client_factory=lambda _s: mock_client,
            settings=settings,
        )
    )

    assert mock_client.repair_async.await_count >= 1
    assert result.repair_attempts >= 1
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
        "figma_flutter_agent.stages.llm_repair.loop.analyze_planned_dart_files",
        fake_analyze,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.reconcile_planned_dart_files",
        lambda planned, **_: planned,
    )

    fixed_generation = FlutterGenerationResponse(screen_code="class FixedScreen {}")
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock(return_value=fixed_generation)

    replanned = {"lib/features/demo/demo_screen.dart": "class Fixed {}"}

    def fake_plan(_request: object) -> MagicMock:
        return MagicMock(planned_files=replanned)

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.replan_planned_files",
        lambda _request, _generation, **_kwargs: replanned,
    )

    result = await run_analyze_repair_loop(
        _repair_request(llm_client_factory=lambda _settings: mock_client)
    )

    mock_client.repair_async.assert_awaited_once()
    assert result.repair_attempts == 1
    assert result.planned_files == replanned
    assert result.llm_result.generation == fixed_generation


def test_repair_patch_has_duplicate_required_this_detects_near_duplicates() -> None:
    generation = FlutterGenerationResponse(
        screen_code="class X {}",
        extracted_widgets=[
            ExtractedWidget(
                widget_name="Bad",
                code=(
                    "const Bad({required this.text, {required this.label, "
                    "required this.onPressed});"
                ),
            )
        ],
    )
    assert _repair_patch_has_duplicate_required_this(generation)


def test_format_failure_paths_from_outcome_falls_back_to_error_lines() -> None:
    outcome = PlannedAnalyzeOutcome(
        skipped=False,
        passed=False,
        detail="dart format failed for generated project",
        errors=(
            "line 71, column 1 of "
            "c:/tmp/analyze_check/lib/features/sign_in/sign_in_screen.dart: "
            "Expected to find ','.",
        ),
        analyze_output="Formatted 1 file\n",
        format_failed_paths=(),
    )
    paths = _format_failure_paths_from_outcome(outcome)
    assert paths == ("lib/features/sign_in/sign_in_screen.dart",)


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_retries_analyzer_timeout_before_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeout = PlannedAnalyzeOutcome(
        skipped=False,
        passed=False,
        detail="dart analyze (generated) (1/3) timed out after 121s",
        toolchain_timeout=True,
    )
    outcomes = [timeout, PlannedAnalyzeOutcome(skipped=False, passed=True, detail="ok")]

    def fake_analyze(*_args: object, **_kwargs: object) -> PlannedAnalyzeOutcome:
        return outcomes.pop(0)

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.analyze_planned_dart_files",
        fake_analyze,
    )
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock(return_value=FlutterGenerationResponse(screen_code="class Ok {}"))

    await run_analyze_repair_loop(
        _repair_request(
            llm_client_factory=lambda _s: mock_client,
            settings=_settings(),
        )
    )
    mock_client.repair_async.assert_not_called()


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_raises_on_repeated_analyzer_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeout = PlannedAnalyzeOutcome(
        skipped=False,
        passed=False,
        detail="dart analyze (generated) (2/3) timed out after 120s",
        toolchain_timeout=True,
    )

    def fake_analyze(*_args: object, **_kwargs: object) -> PlannedAnalyzeOutcome:
        return timeout

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.loop.analyze_planned_dart_files",
        fake_analyze,
    )
    mock_client = MagicMock()
    mock_client.repair_async = AsyncMock()

    with pytest.raises(GenerationError, match="refusing LLM repair"):
        await run_analyze_repair_loop(
            _repair_request(
                llm_client_factory=lambda _s: mock_client,
                settings=_settings(),
            )
        )
    mock_client.repair_async.assert_not_called()
