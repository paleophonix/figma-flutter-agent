"""OpenRouter malformed HTTP body handling."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.clients import OpenRouterLlmClient
from figma_flutter_agent.llm.clients.retry import RetryMixin


def test_openrouter_malformed_body_raises_llm_error_for_retry() -> None:
    mock_client = MagicMock()
    mock_raw = MagicMock()
    mock_raw.text = "   \n  "
    mock_raw.parse.side_effect = json.JSONDecodeError("Expecting value", "", 0)
    mock_client.chat.completions.with_raw_response.create.return_value = mock_raw

    client = OpenRouterLlmClient(api_key="test-key", model="openai/gpt-5.4")
    client._client = mock_client

    with pytest.raises(LlmError, match="malformed JSON body"):
        client._chat_completions_create(model="openai/gpt-5.4", messages=[])


def test_malformed_openrouter_body_is_retryable() -> None:
    exc = LlmError("OpenRouter returned malformed JSON body (preview=''): Expecting value")
    assert RetryMixin._is_retryable(exc) is True
