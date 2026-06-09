from typing import Any
from unittest.mock import patch

import pytest

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.clients import AnthropicLlmClient
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, NodeType


def test_llm_client_retries_on_transient_error() -> None:
    client = AnthropicLlmClient(api_key="test-key", model="claude-sonnet-4-6")

    call_count = 0

    def mock_request_generation(*args: Any, **kwargs: Any) -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            # First two calls raise a retryable rate limit error
            raise LlmError("Rate limited", status_code=429)
        # Third call succeeds and returns standard mock response JSON
        return '{"screenCode": "class TestScreen {}", "extractedWidgets": []}'

    clean_tree = CleanDesignTreeNode(id="1:1", name="Test", type=NodeType.CONTAINER)
    tokens = DesignTokens()

    with (
        patch("time.sleep") as mock_sleep,
        patch.object(client, "_request_generation", side_effect=mock_request_generation),
    ):
        response = client.generate(
            clean_tree,
            tokens,
            feature_name="test",
            asset_manifest=[],
        )

        assert response.screen_code == "class TestScreen {}"
        assert call_count == 3
        # Assert sleep was called twice with exponential backoff
        assert mock_sleep.call_count == 2


def test_llm_client_does_not_retry_on_client_error() -> None:
    client = AnthropicLlmClient(api_key="test-key", model="claude-sonnet-4-6")

    call_count = 0

    def mock_request_generation(*args: Any, **kwargs: Any) -> str:
        nonlocal call_count
        call_count += 1
        # Raise non-retryable 400 Bad Request error
        raise LlmError("Bad request", status_code=400)

    clean_tree = CleanDesignTreeNode(id="1:1", name="Test", type=NodeType.CONTAINER)
    tokens = DesignTokens()

    with (
        patch("time.sleep") as mock_sleep,
        patch.object(client, "_request_generation", side_effect=mock_request_generation),
        pytest.raises(LlmError) as exc_info,
    ):
        client.generate(
            clean_tree,
            tokens,
            feature_name="test",
            asset_manifest=[],
        )

    assert exc_info.value.status_code == 400
    assert call_count == 1
    mock_sleep.assert_not_called()


def test_llm_client_retries_on_json_validation_failure() -> None:
    client = AnthropicLlmClient(api_key="test-key", model="claude-sonnet-4-6")

    call_count = 0

    def mock_request_generation(*args: Any, **kwargs: Any) -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return '{"screenCode": "class TestScreen {'
        return '{"screenCode": "class TestScreen {}", "extractedWidgets": []}'

    clean_tree = CleanDesignTreeNode(id="1:1", name="Test", type=NodeType.CONTAINER)
    tokens = DesignTokens()

    with (
        patch("time.sleep") as mock_sleep,
        patch.object(client, "_request_generation", side_effect=mock_request_generation),
    ):
        response = client.generate(
            clean_tree,
            tokens,
            feature_name="test",
            asset_manifest=[],
        )

    assert response.screen_code == "class TestScreen {}"
    assert call_count == 3
    assert mock_sleep.call_count == 2


def test_coerce_json_text_strips_markdown_fence() -> None:
    from figma_flutter_agent.llm.clients import BaseLlmClient

    raw = """```json
{"screenCode": "class Demo {}", "extractedWidgets": []}
```"""
    assert BaseLlmClient._coerce_json_text(raw).startswith('{"screenCode"')
