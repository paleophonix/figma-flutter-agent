"""Tests for the LLM pipeline stage."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
)
from figma_flutter_agent.stages.llm import LlmStageRequest, run_llm_stage


def _request(**overrides: Any) -> LlmStageRequest:
    base = LlmStageRequest(
        settings=Settings(
            FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
            ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
            LLM_PROVIDER="anthropic",
        ),
        dry_run=False,
        resolved_sync=False,
        tree_changed=True,
        tokens_changed=True,
        previous_snapshot_exists=False,
        clean_tree=CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.CONTAINER),
        tokens=DesignTokens(),
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
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.asyncio
async def test_run_llm_stage_uses_llm_ir_by_default() -> None:
    llm = MagicMock()
    llm.generate_async = AsyncMock(
        return_value=FlutterGenerationResponse(
            screen_ir={"root": {"figmaId": "1:1", "kind": "auto", "children": []}}
        )
    )
    factory = MagicMock(return_value=llm)

    result = await run_llm_stage(_request(llm_client_factory=factory))

    factory.assert_called_once()
    llm.generate_async.assert_awaited_once()
    assert result.generation is not None
    assert result.llm_attempted is True


@pytest.mark.asyncio
async def test_run_llm_stage_skips_when_dry_run() -> None:
    factory = MagicMock()
    result = await run_llm_stage(_request(dry_run=True, llm_client_factory=factory))

    factory.assert_not_called()
    assert result.generation is None


@pytest.mark.asyncio
async def test_run_llm_stage_skips_incremental_theme_only_update() -> None:
    factory = MagicMock()
    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
        agent=AgentYamlConfig(
            generation=GenerationConfig(),
        ),
    )
    result = await run_llm_stage(
        _request(
            settings=settings,
            resolved_sync=True,
            tree_changed=False,
            tokens_changed=True,
            previous_snapshot_exists=True,
            llm_client_factory=factory,
        )
    )

    factory.assert_not_called()
    assert result.skipped_incremental is True


@pytest.mark.asyncio
async def test_run_llm_stage_raises_without_api_key_when_llm_mode() -> None:
    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr(""),
        LLM_PROVIDER="anthropic",
    )
    settings.agent = AgentYamlConfig(
        generation=GenerationConfig(),
    )

    with pytest.raises(LlmError, match="ANTHROPIC_API_KEY"):
        await run_llm_stage(_request(settings=settings))


@pytest.mark.asyncio
async def test_run_llm_stage_generates_primary_screen() -> None:
    request = _request()
    request.settings.agent = AgentYamlConfig(
        generation=GenerationConfig(),
    )
    llm = MagicMock()
    llm.generate_async = AsyncMock(
        return_value=FlutterGenerationResponse(screen_code="class ScreenScreen {}")
    )
    factory = MagicMock(return_value=llm)

    request.llm_client_factory = factory
    result = await run_llm_stage(request)

    factory.assert_called_once()
    llm.generate_async.assert_awaited_once()
    assert result.generation is not None
