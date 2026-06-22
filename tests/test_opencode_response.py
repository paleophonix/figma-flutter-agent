"""Tests for OpenCode prompt response parsing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from figma_flutter_agent.dev.opencode.client import OpenCodeClient
from figma_flutter_agent.dev.opencode.opencode_response import (
    detect_repair_steps_exhausted,
    extract_opencode_assistant_text,
    extract_opencode_prompt_error,
    extract_opencode_token_usage,
    opencode_provider_reached,
)
from figma_flutter_agent.errors import FigmaFlutterError


def test_extract_opencode_prompt_error_reads_provider_auth() -> None:
    response = {
        "info": {
            "error": {
                "name": "ProviderAuthError",
                "data": {
                    "message": "OpenRouter API key is missing.",
                },
            }
        }
    }
    assert extract_opencode_prompt_error(response) == "OpenRouter API key is missing."


def test_extract_opencode_prompt_error_none_when_ok() -> None:
    assert extract_opencode_prompt_error({"info": {"role": "assistant"}}) is None


def test_extract_opencode_assistant_text_joins_text_parts() -> None:
    response = {
        "parts": [
            {"type": "reasoning", "text": "hidden"},
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "World"},
        ],
    }
    assert extract_opencode_assistant_text(response) == "Hello\n\nWorld"


def test_detect_repair_steps_exhausted_explicit_marker() -> None:
    text = "## Maximum steps reached — repair progress summary\n"
    assert detect_repair_steps_exhausted(text) is True


def test_detect_repair_steps_exhausted_remaining_tasks_pattern() -> None:
    text = "What was NOT completed (steps still pending)\nRemaining tasks:\nNext steps:\n"
    assert detect_repair_steps_exhausted(text) is True


def test_detect_repair_steps_exhausted_false_for_empty_noop() -> None:
    assert detect_repair_steps_exhausted("blocked=true; no plan steps") is False


def test_extract_opencode_token_usage_reads_tokens_block() -> None:
    response = {"info": {"tokens": {"input": 12, "output": 3}}}
    assert extract_opencode_token_usage(response) == (12, 3)


def test_opencode_provider_reached_false_on_zero_tokens() -> None:
    assert opencode_provider_reached({"info": {"tokens": {"input": 0, "output": 0}}}) is False


def test_opencode_provider_reached_true_on_tokens() -> None:
    assert opencode_provider_reached({"info": {"tokens": {"input": 1, "output": 0}}}) is True


@pytest.mark.asyncio
async def test_prompt_message_raises_on_timeout() -> None:
    client = OpenCodeClient(base_url="http://127.0.0.1:4096", timeout_sec=5.0)

    async def _timeout_post(*_args: object, **_kwargs: object) -> MagicMock:
        raise httpx.TimeoutException("timed out")

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_timeout_post)):
        with pytest.raises(FigmaFlutterError, match="timed out after 5"):
            await client.prompt_message("sess-1", text="hi", agent="repair")
