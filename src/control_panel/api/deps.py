"""Shared FastAPI dependencies."""

from __future__ import annotations

import hashlib
import secrets
from typing import TYPE_CHECKING, Any

from fastapi import Depends, Header, HTTPException, Request

from control_panel.services.rate_limit import RateLimitExceeded, check_create_job_rate_limit

if TYPE_CHECKING:
    from arq import ArqRedis

    from control_panel.bot.app import DiscordControlBot
    from control_panel.config import DiscordBotSettings
    from control_panel.db.repair_store import RepairJobStore
    from control_panel.db.store import JobStore


def get_settings(request: Request) -> DiscordBotSettings:
    """Return application settings."""
    return request.app.state.settings


def get_store(request: Request) -> JobStore:
    """Return the job store."""
    return request.app.state.store


def get_repair_store(request: Request) -> RepairJobStore:
    """Return the repair job store."""
    return request.app.state.repair_store


def get_bot(request: Request) -> DiscordControlBot | None:
    """Return the Discord bot when enabled."""
    return request.app.state.bot


def get_arq_pool(request: Request) -> ArqRedis:
    """Return the ARQ Redis pool."""
    return request.app.state.arq_pool


def get_redis(request: Request) -> Any:
    """Return the asyncio Redis client for pub/sub and rate limits."""
    return request.app.state.redis


def hash_api_key(raw_key: str) -> str:
    """Return sha256 hex digest for an API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def require_api_enabled(
    settings: DiscordBotSettings = Depends(get_settings),
) -> None:
    """Ensure public API is enabled."""
    if not settings.api_enabled:
        raise HTTPException(status_code=503, detail="api disabled")


def require_principal(
    x_api_key: str = Header(default="", alias="X-API-Key"),
    settings: DiscordBotSettings = Depends(get_settings),
) -> str:
    """Authenticate API requests and return the principal id."""
    if not settings.api_enabled:
        raise HTTPException(status_code=503, detail="api disabled")
    if not x_api_key.strip():
        raise HTTPException(status_code=401, detail="unauthorized")
    digest = hash_api_key(x_api_key.strip())
    for client in settings.api_clients:
        if secrets.compare_digest(client.key_hash, digest):
            return client.principal
    raise HTTPException(status_code=401, detail="unauthorized")


async def enforce_create_job_rate_limit(
    principal: str = Depends(require_principal),
    redis: Any = Depends(get_redis),
    settings: DiscordBotSettings = Depends(get_settings),
) -> None:
    """Apply per-principal and global POST /v1/jobs rate limits."""
    try:
        await check_create_job_rate_limit(redis, settings, principal=principal)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after_sec)},
        ) from exc


def require_metrics_token(
    authorization: str = Header(default=""),
    settings: DiscordBotSettings = Depends(get_settings),
) -> None:
    """Authorize Prometheus scrape requests."""
    expected = settings.metrics_token.get_secret_value().strip()
    if not expected:
        raise HTTPException(status_code=401, detail="unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="unauthorized")
