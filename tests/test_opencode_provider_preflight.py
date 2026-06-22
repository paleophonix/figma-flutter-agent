"""OpenCode → OpenRouter provider preflight smoke."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from figma_flutter_agent.dev.opencode.provider_preflight import (
    verify_opencode_openrouter_connectivity,
)
from figma_flutter_agent.errors import FigmaFlutterError


@pytest.mark.asyncio
async def test_verify_opencode_openrouter_connectivity_ok() -> None:
    with patch(
        "figma_flutter_agent.dev.opencode.provider_preflight.OpenCodeClient",
    ) as client_cls:
        client = client_cls.return_value
        client.create_session = AsyncMock(return_value="sess-preflight")
        client.prompt_message = AsyncMock(
            return_value={"info": {"tokens": {"input": 5, "output": 1}}, "parts": []},
        )
        client.abort_session = AsyncMock()

        await verify_opencode_openrouter_connectivity(
            base_url="http://127.0.0.1:4096",
            model="openrouter/xiaomi/mimo-v2.5-pro",
        )

    client.prompt_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_opencode_openrouter_connectivity_fails_on_zero_tokens() -> None:
    with patch(
        "figma_flutter_agent.dev.opencode.provider_preflight.OpenCodeClient",
    ) as client_cls:
        client = client_cls.return_value
        client.create_session = AsyncMock(return_value="sess-preflight")
        client.prompt_message = AsyncMock(
            return_value={"info": {"tokens": {"input": 0, "output": 0}}, "parts": []},
        )
        client.abort_session = AsyncMock()

        with pytest.raises(FigmaFlutterError, match="zero LLM tokens"):
            await verify_opencode_openrouter_connectivity(
                base_url="http://127.0.0.1:4096",
                model="openrouter/xiaomi/mimo-v2.5-pro",
            )

    client.abort_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_opencode_openrouter_connectivity_fails_on_provider_error() -> None:
    with patch(
        "figma_flutter_agent.dev.opencode.provider_preflight.OpenCodeClient",
    ) as client_cls:
        client = client_cls.return_value
        client.create_session = AsyncMock(return_value="sess-preflight")
        client.prompt_message = AsyncMock(
            return_value={
                "info": {
                    "error": {
                        "name": "ProviderAuthError",
                        "data": {"message": "OpenRouter API key is missing."},
                    }
                }
            },
        )
        client.abort_session = AsyncMock()

        with pytest.raises(FigmaFlutterError, match="OpenRouter API key is missing"):
            await verify_opencode_openrouter_connectivity(
                base_url="http://127.0.0.1:4096",
                model="openrouter/xiaomi/mimo-v2.5-pro",
            )
