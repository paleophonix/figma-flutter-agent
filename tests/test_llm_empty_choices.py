"""Tests for OpenAI-compat completions with missing choices."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.clients import OpenRouterLlmClient
from figma_flutter_agent.llm.prompts import build_system_prompt


def test_request_generation_raises_llm_error_when_choices_none() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = None
    mock_response.id = None
    mock_response.model = None
    mock_response.error = None
    mock_raw = MagicMock()
    mock_raw.text = '{"choices": null}'
    mock_raw.parse.return_value = mock_response
    mock_client.chat.completions.with_raw_response.create.return_value = mock_raw

    client = OpenRouterLlmClient(
        api_key="test-key",
        model="google/gemini-3.5-flash",
        temperature=1.0,
        top_p=0.95,
    )
    client._client = mock_client

    with pytest.raises(LlmError, match="no completion choices"):
        client._request_generation(
            '{"featureName":"sign_in"}',
            system_prompt=build_system_prompt(),
        )
