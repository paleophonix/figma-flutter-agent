"""Automated matrix for LLM incremental skip policy (limitations.md §16)."""

from __future__ import annotations

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
from figma_flutter_agent.stages.llm import LlmStageRequest, _needs_llm, run_llm_stage


def _request(
    *,
    tree_changed: bool,
    tokens_changed: bool,
    regen_on_token_change: bool = False,
    force_llm_regen: bool = False,
    resolved_sync: bool = True,
    previous_snapshot_exists: bool = True,
) -> LlmStageRequest:
    settings = Settings()
    settings.agent = AgentYamlConfig(
        generation=GenerationConfig(
            regen_llm_on_token_change=regen_on_token_change,
        ),
    )
    return LlmStageRequest(
        settings=settings,
        dry_run=False,
        resolved_sync=resolved_sync,
        tree_changed=tree_changed,
        tokens_changed=tokens_changed,
        previous_snapshot_exists=previous_snapshot_exists,
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
        force_llm_regen=force_llm_regen,
    )


@pytest.mark.parametrize(
    ("tree_changed", "tokens_changed", "regen_on_token", "force", "expected"),
    [
        (True, False, False, False, True),
        (False, False, False, False, False),
        (False, True, False, False, False),
        (False, True, True, False, True),
        (False, False, False, True, True),
    ],
)
def test_needs_llm_policy_matrix(
    tree_changed: bool,
    tokens_changed: bool,
    regen_on_token: bool,
    force: bool,
    expected: bool,
) -> None:
    request = _request(
        tree_changed=tree_changed,
        tokens_changed=tokens_changed,
        regen_on_token_change=regen_on_token,
        force_llm_regen=force,
    )
    assert _needs_llm(request) is expected


@pytest.mark.asyncio
async def test_run_llm_stage_skips_when_tree_unchanged_and_tokens_unchanged() -> None:
    request = _request(tree_changed=False, tokens_changed=False)
    result = await run_llm_stage(request)
    assert result.skipped_incremental is True
    assert result.generation is None


@pytest.mark.asyncio
async def test_run_llm_stage_skips_when_tokens_change_without_regen_flag() -> None:
    request = _request(tree_changed=False, tokens_changed=True, regen_on_token_change=False)
    result = await run_llm_stage(request)
    assert result.skipped_incremental is True


@pytest.mark.asyncio
async def test_run_llm_stage_calls_llm_when_tokens_change_with_regen_flag() -> None:
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
    request = _request(tree_changed=False, tokens_changed=True, regen_on_token_change=True)
    request.settings = settings
    llm = MagicMock()
    llm.generate_async = AsyncMock(
        return_value=FlutterGenerationResponse(screen_code="class ScreenScreen {}")
    )
    factory = MagicMock(return_value=llm)
    request.llm_client_factory = factory
    result = await run_llm_stage(request)
    assert result.skipped_incremental is False
    factory.assert_called_once()
    llm.generate_async.assert_awaited_once()
