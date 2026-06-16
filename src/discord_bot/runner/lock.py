"""Per-project asyncio locks for pipeline runs."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path


class ProjectLockRegistry:
    """Serialize pipeline runs per Flutter project directory."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @asynccontextmanager
    async def acquire(self, project_dir: Path) -> AsyncIterator[None]:
        """Hold the lock for one project root."""
        key = project_dir.expanduser().resolve().as_posix()
        async with self._locks[key]:
            yield
