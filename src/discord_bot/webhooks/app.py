"""aiohttp webhook application factory."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from discord_bot.config import DiscordBotSettings
from discord_bot.db import JobStore
from discord_bot.webhooks.gitlab import handle_gitlab_webhook
from discord_bot.webhooks.internal import register_internal_routes


def create_webhook_app(
    *,
    settings: DiscordBotSettings,
    store: JobStore,
    bot: Any,
) -> web.Application:
    """Build the webhook aiohttp application."""
    app = web.Application()

    async def gitlab_handler(request: web.Request) -> web.Response:
        return await handle_gitlab_webhook(
            request,
            store=store,
            expected_token=settings.yaml.internal.gitlab_webhook_secret,
            bot=bot,
        )

    app.router.add_post("/webhooks/gitlab", gitlab_handler)
    register_internal_routes(
        app,
        store=store,
        expected_secret=settings.yaml.internal.callback_secret,
        bot=bot,
    )
    return app


def parse_bind(bind: str) -> tuple[str, int]:
    """Parse ``host:port`` bind string."""
    host, _, port_text = bind.partition(":")
    port = int(port_text or "8787")
    return host or "127.0.0.1", port
