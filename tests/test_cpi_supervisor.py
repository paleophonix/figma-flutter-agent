"""Tests for CPI repair-loop supervisor wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from figma_flutter_agent.generator.validation import PlannedAnalyzeOutcome
from figma_flutter_agent.llm.prompts import (
    CpiSupervisorContext,
    render_cpi_supervisor_prompt,
    render_repair_system_prompt,
)
from figma_flutter_agent.llm.repair_scope import RepairEnvironmentContext
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ExtractedWidget,
    FlutterGenerationResponse,
    NodeType,
    RepairCpiSupervisorResponse,
)
from figma_flutter_agent.stages.llm import LlmStageResult
from figma_flutter_agent.stages.llm_repair import run_analyze_repair_loop
from tests.test_llm_repair import _repair_request, _settings


def test_render_cpi_supervisor_prompt_matches_acdp_layers() -> None:
    context = CpiSupervisorContext(
        last_patches='["Attempt 1 (failed): patch"]',
        recurring_errors="- error - foo.dart:1:1 - isn't a class",
        figma_node_intent='{"id": "1:1", "name": "Screen"}',
    )
    prompt = render_cpi_supervisor_prompt(context)
    assert "<L1:PURPOSE>" in prompt
    assert "Metacognitive Code-Review Supervisor" in prompt
    assert "ANTI-PATTERN INERTIA" in prompt
    assert "isn't a class" in prompt


def test_repair_system_prompt_injects_cpi_directive() -> None:
    context = RepairEnvironmentContext(
        analyze_errors="- error - x",
        code="1: class X {}",
        semantic_hint="null",
        failed_attempts_history="(no prior failed patches in this run)",
        unchanged_widget_names="(none)",
        cpi_supervisor_directive="REPLACE _AmbientBackground WITH AmbientBackground IN screenCode",
    )
    prompt = render_repair_system_prompt(context)
    assert "CPI Supervisor Pattern Interrupt" in prompt
    assert "REPLACE _AmbientBackground" in prompt


@pytest.mark.asyncio
async def test_run_analyze_repair_loop_invokes_cpi_on_stagnation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drift_error = (
        "error - lib/features/sign_in/sign_in_screen.dart:64:29 - creation_with_non_type - "
        "The name '_AmbientBackground' isn't a class"
    )
    outcomes = [
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="flutter analyze failed",
            errors=(drift_error,),
        ),
        PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail="flutter analyze failed",
            errors=(drift_error,),
        ),
        PlannedAnalyzeOutcome(skipped=False, passed=True, detail="ok"),
    ]

    def fake_analyze(*_args: object, **_kwargs: object) -> PlannedAnalyzeOutcome:
        return outcomes.pop(0) if outcomes else PlannedAnalyzeOutcome(
            skipped=False,
            passed=True,
            detail="ok",
        )

    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.analyze_planned_dart_files",
        fake_analyze,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.reconcile_planned_dart_files",
        lambda planned, **_: planned,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.stages.llm_repair.replan_planned_files",
        lambda _request, generation, **_kwargs: {
            "lib/features/sign_in/sign_in_screen.dart": generation.screen_code,
        },
    )

    mock_client = MagicMock()
    mock_client.cpi_supervisor_async = AsyncMock(
        return_value=RepairCpiSupervisorResponse(
            analysis="Agent keeps private widget names in screenCode.",
            pattern_interrupt_directive="RENAME ALL _AmbientBackground TO AmbientBackground",
        ),
    )
    mock_client.repair_async = AsyncMock(
        side_effect=[
            FlutterGenerationResponse(screen_code="class StillBad {}"),
            FlutterGenerationResponse(screen_code="class Fixed {}"),
        ],
    )

    base_settings = _settings()
    settings = base_settings.model_copy(
        update={
            "agent": base_settings.agent.model_copy(
                update={
                    "generation": base_settings.agent.generation.model_copy(
                        update={
                            "llm_repair_max_attempts": 3,
                            "llm_repair_cpi_supervisor": True,
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
            llm_result=LlmStageResult(
                generation=FlutterGenerationResponse(
                    screen_code="class Bad { Widget build(_) => _AmbientBackground(); }",
                    extracted_widgets=[
                        ExtractedWidget(
                            widget_name="AmbientBackground",
                            code="class _AmbientBackground extends StatelessWidget {}",
                        ),
                    ],
                ),
            ),
            clean_tree=CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.CONTAINER),
        )
    )

    mock_client.cpi_supervisor_async.assert_awaited_once()
    assert mock_client.repair_async.await_count == 1
    last_repair_kwargs = mock_client.repair_async.await_args_list[-1].kwargs
    assert last_repair_kwargs["cpi_supervisor_directive"] == (
        "RENAME ALL _AmbientBackground TO AmbientBackground"
    )
    assert result.repair_attempts == 2
