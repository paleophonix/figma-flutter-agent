"""Health, readiness, and metrics routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select

from control_panel.api.deps import get_redis, get_repair_store, get_store, require_metrics_token
from control_panel.db.models import GenerationJobRow
from control_panel.db.repair_store import RepairJobStore
from control_panel.db.store import JobStore
from figma_flutter_agent.observability.prometheus_metrics import (
    metrics_content_type,
    refresh_jobs_snapshot,
    refresh_repair_jobs_snapshot,
    render_metrics,
    set_component_ready,
)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    store: JobStore = Depends(get_store),
    redis: Any = Depends(get_redis),
) -> Response:
    """Readiness probe for Postgres and Redis."""
    try:
        await store.ping()
        if redis is not None:
            await redis.ping()
    except Exception:
        return Response(
            content='{"status":"unavailable"}', status_code=503, media_type="application/json"
        )
    return Response(content='{"status":"ready"}', media_type="application/json")


@router.get("/metrics")
async def metrics(
    store: JobStore = Depends(get_store),
    repair_store: RepairJobStore = Depends(get_repair_store),
    redis: Any = Depends(get_redis),
    _: None = Depends(require_metrics_token),
) -> Response:
    """Prometheus metrics (internal scrape only)."""
    postgres_ok = True
    redis_ok = True
    try:
        await store.ping()
    except Exception:
        postgres_ok = False
    try:
        if redis is not None:
            await redis.ping()
    except Exception:
        redis_ok = False
    set_component_ready("postgres", postgres_ok)
    set_component_ready("redis", redis_ok)

    async with store._session_factory() as session:  # noqa: SLF001
        result = await session.execute(
            select(
                GenerationJobRow.status,
                GenerationJobRow.origin,
                func.count(),
            ).group_by(GenerationJobRow.status, GenerationJobRow.origin)
        )
        job_counts = {
            (str(status), str(origin)): int(count) for status, origin, count in result.all()
        }
    refresh_jobs_snapshot(job_counts)

    repair_counts = await repair_store.count_by_status()
    refresh_repair_jobs_snapshot(repair_counts)

    body = render_metrics()
    return Response(content=body, media_type=metrics_content_type())
