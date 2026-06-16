"""Redis distributed locks for pipeline runs."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis


class RedisProjectLock:
    """Serialize pipeline runs per project directory using Redis."""

    def __init__(self, redis: Redis, *, ttl_sec: int = 3600) -> None:
        self._redis = redis
        self._ttl_sec = ttl_sec

    @asynccontextmanager
    async def acquire(self, project_key: str) -> AsyncIterator[None]:
        """Hold a distributed lock for one project key."""
        lock = self._redis.lock(f"figma-cp:project:{project_key}", timeout=self._ttl_sec)
        await lock.acquire()
        try:
            yield
        finally:
            await lock.release()
