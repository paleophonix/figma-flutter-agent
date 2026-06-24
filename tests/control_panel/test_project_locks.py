"""Tests for Redis project pipeline locks."""

from __future__ import annotations

import pytest
from redis.asyncio import Redis

from control_panel.workers.locks import (
    force_release_project_lock,
    project_lock_key,
    purge_orphan_project_locks,
)


@pytest.mark.asyncio
async def test_force_release_project_lock() -> None:
    redis = Redis.from_url("redis://127.0.0.1:6379/15", decode_responses=False)
    project_key = "E:/tmp/test-sandbox"
    key = project_lock_key(project_key)
    try:
        await redis.set(key, b"stale")
        assert await force_release_project_lock(redis, project_key) is True
        assert await redis.exists(key) == 0
        assert await force_release_project_lock(redis, project_key) is False
    finally:
        await redis.delete(key)
        await redis.aclose()


@pytest.mark.asyncio
async def test_purge_orphan_project_locks() -> None:
    redis = Redis.from_url("redis://127.0.0.1:6379/15", decode_responses=False)
    key = project_lock_key("E:/tmp/purge-me")
    try:
        await redis.set(key, b"stale")
        deleted = await purge_orphan_project_locks(redis)
        assert deleted >= 1
        assert await redis.exists(key) == 0
    finally:
        await redis.delete(key)
        await redis.aclose()
