"""FastAPI application factory and lifespan."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from loguru import logger

from discord_bot.api.routers import health, internal, telegram, webhooks
from discord_bot.bot.app import DiscordControlBot
from discord_bot.bot.commands.autoclose import register_autoclose_command
from discord_bot.bot.commands.generate import register_generate_command
from discord_bot.bot.commands.repo import register_repo_command
from discord_bot.bot.commands.telegram import register_telegram_command
from discord_bot.config import load_discord_bot_settings
from discord_bot.db.engine import create_engine, create_session_factory
from discord_bot.db.models import Base
from discord_bot.db.store import JobStore


def parse_bind(bind: str) -> tuple[str, int]:
    """Parse ``host:port`` bind string."""
    host, _, port_text = bind.partition(":")
    port = int(port_text or "8787")
    return host or "127.0.0.1", port


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Discord bot and ARQ pool; stop on shutdown."""
    settings = load_discord_bot_settings()
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    store = JobStore(session_factory)

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    arq_pool = await create_pool(redis_settings)

    bot = DiscordControlBot(settings=settings, store=store, arq_pool=arq_pool)
    register_generate_command(bot)
    register_repo_command(bot)
    register_telegram_command(bot)
    register_autoclose_command(bot)

    app.state.settings = settings
    app.state.store = store
    app.state.bot = bot
    app.state.arq_pool = arq_pool
    app.state.engine = engine

    bot_task = asyncio.create_task(bot.start(settings.discord_bot_token.get_secret_value()))
    logger.info("Control plane started")
    try:
        yield
    finally:
        bot_task.cancel()
        with suppress(asyncio.CancelledError):
            await bot_task
        await arq_pool.close()
        await engine.dispose()
        logger.info("Control plane stopped")


app = FastAPI(title="figma-flutter control plane", lifespan=lifespan)
app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(telegram.router)
app.include_router(internal.router)
