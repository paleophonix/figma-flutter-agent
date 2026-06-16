"""Discord bot test fixtures."""

from __future__ import annotations

import os

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from control_panel.db.engine import create_session_factory
from control_panel.db.models import Base
from control_panel.db.store import JobStore


def _database_url() -> str | None:
    return os.getenv("FIGMA_CP_DATABASE_URL")


@pytest.fixture
async def pg_engine() -> AsyncEngine:
    """Yield a PostgreSQL engine for control plane tests."""
    url = _database_url()
    if not url:
        pytest.skip("FIGMA_CP_DATABASE_URL is not set")
    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def job_store(pg_engine: AsyncEngine) -> JobStore:
    """Yield a job store backed by PostgreSQL."""
    factory = create_session_factory(pg_engine)
    return JobStore(factory)
