"""Discord /generate slash command behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from control_panel.bot.commands.generate import register_generate_command
from control_panel.config.models import DiscordBotYamlConfig
from figma_flutter_agent.errors import FigmaUrlError


class _FakeDiscordControlBot:
    """Minimal bot stand-in for slash handler tests."""

    def __init__(self) -> None:
        self.settings = MagicMock()
        self.settings.yaml = DiscordBotYamlConfig.model_validate(
            {"discord": {"access": {"mode": "everyone"}}},
        )
        self.job_store = AsyncMock()
        self.arq_pool = MagicMock()


def _capture_generate_handler(bot: _FakeDiscordControlBot):
    handler_holder: dict[str, object] = {}

    def slash_command(*_args, **_kwargs):
        def decorator(fn):
            fn.autocomplete = lambda _name: lambda autocomplete_fn: autocomplete_fn
            handler_holder["fn"] = fn
            return fn

        return decorator

    bot.slash_command = slash_command  # type: ignore[attr-defined]
    register_generate_command(bot)  # type: ignore[arg-type]
    return handler_holder["fn"]


@pytest.mark.asyncio
async def test_generate_defers_before_url_validation(monkeypatch) -> None:
    """Discord interactions must be acknowledged before heavy validation work."""
    call_order: list[str] = []

    monkeypatch.setattr(
        "control_panel.bot.app.DiscordControlBot",
        _FakeDiscordControlBot,
    )
    monkeypatch.setattr(
        "control_panel.bot.commands.generate.parse_figma_url",
        lambda _url: call_order.append("parse"),
    )
    monkeypatch.setattr(
        "control_panel.bot.commands.generate.resolve_active_repo_key",
        AsyncMock(return_value="demo"),
    )
    monkeypatch.setattr(
        "control_panel.bot.commands.generate.resolve_repo_config",
        lambda *_args, **_kwargs: MagicMock(),
    )
    enqueue = AsyncMock(return_value=MagicMock(job_id="job-1"))
    monkeypatch.setattr("control_panel.bot.commands.generate.enqueue_generation", enqueue)

    bot = _FakeDiscordControlBot()
    handler = _capture_generate_handler(bot)

    inter = MagicMock()
    inter.author.id = 1
    inter.channel_id = 2
    inter.response.defer = AsyncMock(side_effect=lambda: call_order.append("defer"))
    inter.response.send_message = AsyncMock()
    inter.edit_original_response = AsyncMock(return_value=MagicMock(id=99))

    await handler(
        inter,
        figma_url="https://www.figma.com/design/AbCdEf/Test?node-id=1-2",
        mode="new",
        target_file=None,
    )

    assert call_order[:2] == ["defer", "parse"]


@pytest.mark.asyncio
async def test_generate_invalid_url_uses_edit_after_defer(monkeypatch) -> None:
    monkeypatch.setattr(
        "control_panel.bot.app.DiscordControlBot",
        _FakeDiscordControlBot,
    )
    monkeypatch.setattr(
        "control_panel.bot.commands.generate.parse_figma_url",
        MagicMock(side_effect=FigmaUrlError("bad url")),
    )

    bot = _FakeDiscordControlBot()
    handler = _capture_generate_handler(bot)

    inter = MagicMock()
    inter.author.id = 1
    inter.response.defer = AsyncMock()
    inter.response.send_message = AsyncMock()
    inter.edit_original_response = AsyncMock()

    await handler(inter, figma_url="not-a-url", mode="new", target_file=None)

    inter.response.defer.assert_awaited_once()
    inter.edit_original_response.assert_awaited_once()
    inter.response.send_message.assert_not_awaited()
