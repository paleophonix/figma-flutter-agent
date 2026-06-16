"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from arq import ArqRedis

    from discord_bot.bot.app import DiscordControlBot
    from discord_bot.config import DiscordBotSettings
    from discord_bot.db.store import JobStore


def get_settings(request: Request) -> DiscordBotSettings:
    """Return application settings."""
    return request.app.state.settings


def get_store(request: Request) -> JobStore:
    """Return the job store."""
    return request.app.state.store


def get_bot(request: Request) -> DiscordControlBot:
    """Return the Discord bot."""
    return request.app.state.bot


def get_arq_pool(request: Request) -> ArqRedis:
    """Return the ARQ Redis pool."""
    return request.app.state.arq_pool
