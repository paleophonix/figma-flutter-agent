"""ARQ worker configuration."""

from __future__ import annotations

import os

from arq.connections import RedisSettings

from discord_bot.workers import tasks


class WorkerSettings:
    """ARQ worker settings."""

    functions = [tasks.run_generation_job, tasks.publish_job, tasks.feedback_issue_job]
    on_startup = tasks.on_startup
    on_shutdown = tasks.on_shutdown
    redis_settings = RedisSettings.from_dsn(
        os.getenv("FIGMA_CP_REDIS_URL", "redis://127.0.0.1:6379/0")
    )
    max_tries = 2
    job_timeout = 3600
