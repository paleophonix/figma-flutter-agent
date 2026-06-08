"""Tests for LLM incremental skip policy when design tokens change."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
)
from figma_flutter_agent.stages.llm import LlmStageRequest, run_llm_stage


@pytest.mark.asyncio
async def test_run_llm_stage_regenerates_when_tokens_change_and_flag_enabled() -> None:
    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("figd_test"),
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        LLM_PROVIDER="anthropic",
    )
    settings.agent = AgentYamlConfig(
        generation=GenerationConfig(
                        regen_llm_on_token_change=True,
        ),
    )
    request = LlmStageRequest(
        settings=settings,
        dry_run=False,
        resolved_sync=True,
        tree_changed=False,
        tokens_changed=True,
        previous_snapshot_exists=True,
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

    llm = MagicMock()
    llm.generate_async = AsyncMock(
        return_value=FlutterGenerationResponse(screen_code="class ScreenScreen {}")
    )
    factory = MagicMock(return_value=llm)
    request.llm_client_factory = factory
    result = await run_llm_stage(request)

    factory.assert_called_once()
    assert result.skipped_incremental is False
    assert result.generation is not None
