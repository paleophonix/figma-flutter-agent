"""Async LLM retry must not block the event loop on backoff."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.clients import AnthropicLlmClient
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, NodeType


@pytest.mark.asyncio
async def test_generate_async_retries_with_asyncio_sleep() -> None:
    client = AnthropicLlmClient(api_key="test-key", model="claude-sonnet-4-6")
    call_count = 0

    def mock_request_generation(*_args: Any, **_kwargs: Any) -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise LlmError("Rate limited", status_code=429)
        return '{"screenIr": {"root": {"figmaId": "1:1", "kind": "auto"}}, "extractedWidgets": []}'

    clean_tree = CleanDesignTreeNode(id="1:1", name="Test", type=NodeType.CONTAINER)
    tokens = DesignTokens()

    with (
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch("time.sleep") as sync_sleep,
        patch.object(client, "_request_generation", side_effect=mock_request_generation),
    ):
        response = await client.generate_async(
            clean_tree,
            tokens,
            feature_name="test",
            asset_manifest=[],
        )

    assert response.screen_ir is not None
    assert response.screen_ir.root.figma_id == "1:1"
    assert call_count == 3
    assert mock_sleep.await_count == 2
    sync_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_generate_async_retries_on_json_validation_failure() -> None:
    client = AnthropicLlmClient(api_key="test-key", model="claude-sonnet-4-6")
    call_count = 0

    def mock_request_generation(*_args: Any, **_kwargs: Any) -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return '{"screenIr": {"root": {"figmaId": "1:1", "kind": "auto"'
        return '{"screenIr": {"root": {"figmaId": "1:1", "kind": "auto"}}, "extractedWidgets": []}'

    clean_tree = CleanDesignTreeNode(id="1:1", name="Test", type=NodeType.CONTAINER)
    tokens = DesignTokens()

    with (
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch.object(client, "_request_generation", side_effect=mock_request_generation),
    ):
        response = await client.generate_async(
            clean_tree,
            tokens,
            feature_name="test",
            asset_manifest=[],
        )

    assert response.screen_ir is not None
    assert response.screen_ir.root.figma_id == "1:1"
    assert call_count == 2
    assert mock_sleep.await_count == 1
