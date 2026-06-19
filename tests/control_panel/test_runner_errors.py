"""Tests for control-plane pipeline failure messages."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from control_panel.runner.errors import enrich_failure_message, format_generation_failure_message
from figma_flutter_agent.errors import FigmaApiError


def test_format_generation_failure_message_figma_404() -> None:
    exc = FigmaApiError('{"status":404,"error":true,"message":"Not found"}', status_code=404)
    text = format_generation_failure_message(exc)
    assert "404" in text
    assert "FIGMA_ACCESS_TOKEN" in text
    assert "Community" in text


def test_format_generation_failure_message_figma_403() -> None:
    exc = FigmaApiError("forbidden", status_code=403)
    text = format_generation_failure_message(exc)
    assert "403" in text
    assert "FIGMA_ACCESS_TOKEN" in text


def test_enrich_failure_message_wraps_raw_figma_404_json() -> None:
    raw = '{"status":404,"error":true,"message":"Not found"}'
    text = enrich_failure_message(raw)
    assert "Figma API 404:" in text
    assert "Community" in text
    assert raw in text


@pytest.mark.asyncio
async def test_on_message_handles_feedback_without_super(monkeypatch) -> None:
    from control_panel.bot.app import DiscordControlBot

    handler = AsyncMock(return_value=False)
    monkeypatch.setattr("control_panel.bot.app.handle_feedback_comment_message", handler)

    bot = MagicMock(spec=DiscordControlBot)
    message = MagicMock()

    await DiscordControlBot.on_message(bot, message)

    handler.assert_awaited_once_with(bot, message)
