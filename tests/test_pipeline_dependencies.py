"""Tests for injectable pipeline composition root."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.generator.writer import DartWriter
from figma_flutter_agent.llm.clients.core import OpenRouterLlmClient
from figma_flutter_agent.pipeline.deps import default_pipeline_dependencies
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
)
from figma_flutter_agent.stages.llm import LlmStageRequest, run_llm_stage
from figma_flutter_agent.stages.write import WriteStageRequest


def test_repair_client_uses_resolved_reasoning() -> None:
    settings = Settings(
        OPENROUTER_API_KEY=SecretStr("sk-or-test"),
        LLM_PROVIDER="openrouter",
        LLM_GENERATE_MODEL="google/gemini-3.5-flash",
        LLM_REPAIR_MODEL="google/gemini-3-flash-preview",
        LLM_REASONING_EFFORT="medium",
        LLM_REASONING_EXCLUDE="true",
    )
    deps = default_pipeline_dependencies()
    client = deps.create_llm_repair_client(settings)
    assert isinstance(client, OpenRouterLlmClient)
    assert client._reasoning_settings.is_active()
    assert client._reasoning_settings.effort == "medium"
    assert client._reasoning_settings.exclude is True
    assert client._include_reasoning()
    assert client._temperature == settings.resolved_llm_repair_temperature()


def test_default_pipeline_dependencies_exposes_factories() -> None:
    deps = default_pipeline_dependencies()
    assert callable(deps.figma_connector)
    assert callable(deps.create_llm_client)
    assert callable(deps.create_llm_repair_client)
    assert callable(deps.create_llm_refine_client)
    assert callable(deps.commit_planned_files)
    assert callable(deps.dart_writer_factory)


def test_dart_writer_factory_creates_writer(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    deps = default_pipeline_dependencies()
    writer = deps.dart_writer_factory(project_dir, enable_backup=False, strict_preservation=True)
    assert isinstance(writer, DartWriter)


@pytest.mark.asyncio
async def test_run_llm_stage_uses_injected_llm_client_factory() -> None:
    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
    )
    settings.agent = AgentYamlConfig(
        generation=GenerationConfig(use_deterministic_screen=False),
    )
    tree = CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.COLUMN)
    tokens = DesignTokens()
    mock_client = MagicMock()
    mock_client.generate_async = AsyncMock(
        return_value=FlutterGenerationResponse(screen_code="class Screen {}")
    )

    def factory(_settings: Settings) -> MagicMock:
        return mock_client

    request = LlmStageRequest(
        settings=settings,
        dry_run=False,
        resolved_sync=False,
        tree_changed=True,
        tokens_changed=False,
        previous_snapshot_exists=False,
        clean_tree=tree,
        tokens=tokens,
        resolved_feature="screen",
        asset_manifest=AssetManifest(),
        widget_hints=[],
        navigation_hints=[],
        routing_on=False,
        navigation_plan=MagicMock(routes=[]),
        frame_index={},
        published_styles={},
        components={},
        component_sets={},
        destination_trees={},
        destination_widget_hints={},
        style_paint_index={},
        llm_client_factory=factory,
    )

    result = await run_llm_stage(request)

    mock_client.generate_async.assert_awaited_once()
    assert result.generation is not None


def test_write_stage_request_accepts_dart_writer_factory(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    captured: list[Path] = []

    def factory(
        path: Path,
        *,
        enable_backup: bool,
        strict_preservation: bool,
    ) -> DartWriter:
        captured.append(path)
        return DartWriter(
            path, enable_backup=enable_backup, strict_preservation=strict_preservation
        )

    request = WriteStageRequest(
        project_dir=project_dir,
        files_to_write={},
        asset_manifest=AssetManifest(),
        routing_type="none",
        state_management_type="none",
        dart_writer_factory=factory,
    )

    assert request.dart_writer_factory is factory
    writer = request.dart_writer_factory(project_dir, enable_backup=True, strict_preservation=False)
    assert captured == [project_dir]
    assert isinstance(writer, DartWriter)
