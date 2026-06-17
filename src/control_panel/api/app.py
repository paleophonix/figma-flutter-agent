"""FastAPI application factory and lifespan."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from loguru import logger
from redis.asyncio import Redis

from control_panel.api.middleware import PrometheusMiddleware
from control_panel.api.routers import health, internal, jobs, repair_jobs, telegram, webhooks
from control_panel.bot.app import DiscordControlBot
from control_panel.bot.commands.autoclose import register_autoclose_command
from control_panel.bot.commands.generate import register_generate_command
from control_panel.bot.commands.repo import register_repo_command
from control_panel.bot.commands.telegram import register_telegram_command
from control_panel.config import load_discord_bot_settings
from control_panel.db.engine import create_engine, create_session_factory
from control_panel.db.models import Base
from control_panel.db.repair_store import RepairJobStore
from control_panel.db.store import JobStore
from control_panel.services.telegram_webhook import register_telegram_webhook


def parse_bind(bind: str) -> tuple[str, int]:
    """Parse ``host:port`` bind string."""
    host, _, port_text = bind.partition(":")
    port = int(port_text or "8787")
    return host or "127.0.0.1", port


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start optional Discord bot, ARQ pool, and Redis; stop on shutdown."""
    settings = load_discord_bot_settings(require_discord_token=False)
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    store = JobStore(session_factory)
    repair_store = RepairJobStore(session_factory)

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    arq_pool = await create_pool(redis_settings)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    bot: DiscordControlBot | None = None
    bot_task: asyncio.Task[None] | None = None
    discord_enabled = settings.yaml.discord.enabled
    token = settings.discord_bot_token.get_secret_value().strip()
    if discord_enabled and token:
        bot = DiscordControlBot(settings=settings, store=store, arq_pool=arq_pool)
        register_generate_command(bot)
        register_repo_command(bot)
        register_telegram_command(bot)
        register_autoclose_command(bot)
        bot_task = asyncio.create_task(bot.start(token))
        logger.info("Discord bot started")
    elif discord_enabled:
        logger.warning("Discord enabled but DISCORD_BOT_TOKEN is empty; bot not started")
    else:
        logger.info("Discord bot disabled (discord.enabled=false)")

    app.state.settings = settings
    app.state.store = store
    app.state.repair_store = repair_store
    app.state.bot = bot
    app.state.arq_pool = arq_pool
    app.state.redis = redis
    app.state.engine = engine

    await register_telegram_webhook(settings)

    logger.info("Control panel started")
    try:
        yield
    finally:
        if bot_task is not None:
            bot_task.cancel()
            with suppress(asyncio.CancelledError):
                await bot_task
        await arq_pool.close()
        await redis.aclose()
        await engine.dispose()
        logger.info("Control panel stopped")


app = FastAPI(title="figma-flutter control panel", lifespan=lifespan)
app.add_middleware(PrometheusMiddleware)
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(repair_jobs.router)
app.include_router(webhooks.router)
app.include_router(telegram.router)
app.include_router(internal.router)
