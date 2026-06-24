"""Redis distributed locks for pipeline runs."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from loguru import logger
from redis.asyncio import Redis

from figma_flutter_agent.errors import FigmaFlutterError

PROJECT_LOCK_PREFIX = "figma-cp:project:"
DEFAULT_LOCK_TTL_SEC = 3600
DEFAULT_LOCK_WAIT_SEC = 120


def project_lock_key(project_key: str) -> str:
    """Return the Redis key for one project directory lock."""
    return f"{PROJECT_LOCK_PREFIX}{project_key}"


async def force_release_project_lock(redis: Redis, project_key: str) -> bool:
    """Delete a project lock key (used before forced cold regen).

    Args:
        redis: Redis client (``decode_responses=False`` for lock tokens).
        project_key: Sandbox directory path used as the lock identity.

    Returns:
        True when a lock key existed and was deleted.
    """
    deleted = await redis.delete(project_lock_key(project_key))
    return bool(deleted)


async def purge_orphan_project_locks(redis: Redis) -> int:
    """Delete all project pipeline lock keys.

    Args:
        redis: Redis client (``decode_responses=False`` for lock tokens).

    Returns:
        Number of deleted lock keys.
    """
    keys: list[bytes | str] = []
    async for key in redis.scan_iter(match=f"{PROJECT_LOCK_PREFIX}*"):
        keys.append(key)
    if not keys:
        return 0
    return int(await redis.delete(*keys))


class RedisProjectLock:
    """Serialize pipeline runs per project directory using Redis."""

    def __init__(
        self,
        redis: Redis,
        *,
        ttl_sec: int = DEFAULT_LOCK_TTL_SEC,
        blocking_timeout_sec: float = DEFAULT_LOCK_WAIT_SEC,
    ) -> None:
        self._redis = redis
        self._ttl_sec = ttl_sec
        self._blocking_timeout_sec = blocking_timeout_sec

    @asynccontextmanager
    async def acquire(self, project_key: str) -> AsyncIterator[None]:
        """Hold a distributed lock for one project key.

        Args:
            project_key: Sandbox directory path used as the lock identity.

        Raises:
            FigmaFlutterError: When the lock cannot be acquired within the wait budget.
        """
        lock = self._redis.lock(project_lock_key(project_key), timeout=self._ttl_sec)
        logger.info(
            "Waiting for project pipeline lock key={} timeout_sec={}",
            project_key,
            self._blocking_timeout_sec,
        )
        acquired = await lock.acquire(
            blocking=True,
            blocking_timeout=self._blocking_timeout_sec,
        )
        if not acquired:
            msg = (
                f"Timed out waiting for pipeline lock on {project_key} "
                f"after {self._blocking_timeout_sec:.0f}s. "
                "Another generation may still be running, or a stale lock remains after a worker crash. "
                "Retry /regen or restart the control panel worker."
            )
            raise FigmaFlutterError(msg)
        logger.info("Acquired project pipeline lock key={}", project_key)
        try:
            yield
        finally:
            await lock.release()
            logger.info("Released project pipeline lock key={}", project_key)
