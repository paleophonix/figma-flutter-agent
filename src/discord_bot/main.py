"""Discord bot, webhook server, and job runner entrypoint."""

from __future__ import annotations

import asyncio

from aiohttp import web
from loguru import logger

from discord_bot.bot.app import DiscordControlBot
from discord_bot.bot.commands.generate import register_generate_command
from discord_bot.config import load_discord_bot_settings
from discord_bot.db import JobStore
from discord_bot.runner.lock import ProjectLockRegistry
from discord_bot.runner.worker import JobWorker
from discord_bot.webhooks.app import create_webhook_app, parse_bind
from figma_flutter_agent.logging_setup import configure_logging


async def _start_webhook_server(
    app: web.Application,
    *,
    bind: str,
) -> web.AppRunner:
    host, port = parse_bind(bind)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    logger.info("Webhook server listening on {}:{}", host, port)
    return runner


async def amain() -> None:
    """Run bot, worker, and webhook server concurrently."""
    configure_logging(verbose=False)
    settings = load_discord_bot_settings()
    store = JobStore(settings.db_path)
    bot = DiscordControlBot(settings=settings, store=store)
    register_generate_command(bot)
    locks = ProjectLockRegistry()
    worker = JobWorker(settings=settings, store=store, bot=bot, locks=locks)
    webhook_app = create_webhook_app(settings=settings, store=store, bot=bot)

    webhook_runner = await _start_webhook_server(
        webhook_app,
        bind=settings.yaml.internal.webhook_bind,
    )
    worker_task = asyncio.create_task(worker.run_forever())
    try:
        await bot.start(settings.discord_bot_token.get_secret_value())
    finally:
        worker_task.cancel()
        await webhook_runner.cleanup()


def main() -> None:
    """CLI entrypoint."""
    asyncio.run(amain())


if __name__ == "__main__":
    main()
