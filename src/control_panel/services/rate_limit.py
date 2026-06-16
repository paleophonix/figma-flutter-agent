"""Redis-backed rate limits for public API."""

from __future__ import annotations

import time
from typing import Any

from control_panel.config import DiscordBotSettings


class RateLimitExceeded(Exception):
    """Raised when a client exceeds configured request limits."""

    def __init__(self, retry_after_sec: int) -> None:
        self.retry_after_sec = retry_after_sec
        super().__init__("rate limit exceeded")


async def check_create_job_rate_limit(
    redis: Any,
    settings: DiscordBotSettings,
    *,
    principal: str,
) -> None:
    """Enforce per-principal and global POST /v1/jobs limits."""
    if redis is None:
        return
    window = 60
    now = int(time.time())
    bucket = now // window
    principal_key = f"control_panel:ratelimit:jobs:{principal}:{bucket}"
    global_key = f"control_panel:ratelimit:jobs:global:{bucket}"

    principal_count = await redis.incr(principal_key)
    if principal_count == 1:
        await redis.expire(principal_key, window)
    global_count = await redis.incr(global_key)
    if global_count == 1:
        await redis.expire(global_key, window)

    if principal_count > settings.api_rate_limit_jobs_per_min:
        raise RateLimitExceeded(retry_after_sec=window - (now % window))
    if global_count > settings.api_rate_limit_jobs_global_per_min:
        raise RateLimitExceeded(retry_after_sec=window - (now % window))
