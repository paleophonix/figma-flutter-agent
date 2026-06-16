"""Health, readiness, and metrics routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select

from control_panel.api.deps import get_redis, get_store, require_metrics_token
from control_panel.db.models import GenerationJobRow
from control_panel.db.store import JobStore

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
        return Response(content='{"status":"unavailable"}', status_code=503, media_type="application/json")
    return Response(content='{"status":"ready"}', media_type="application/json")


@router.get("/metrics")
async def metrics(
    store: JobStore = Depends(get_store),
    redis: Any = Depends(get_redis),
    _: None = Depends(require_metrics_token),
) -> Response:
    """Prometheus metrics (internal scrape only)."""
    lines = [
        "# HELP control_panel_ready Component readiness (1=ok).",
        "# TYPE control_panel_ready gauge",
    ]
    postgres_ok = 1
    redis_ok = 1
    try:
        await store.ping()
    except Exception:
        postgres_ok = 0
    try:
        if redis is not None:
            await redis.ping()
    except Exception:
        redis_ok = 0
    lines.append(f'control_panel_ready{{component="postgres"}} {postgres_ok}')
    lines.append(f'control_panel_ready{{component="redis"}} {redis_ok}')
    lines.extend(
        [
            "# HELP control_panel_jobs_total Jobs grouped by status and origin.",
            "# TYPE control_panel_jobs_total gauge",
        ]
    )
    async with store._session_factory() as session:  # noqa: SLF001
        result = await session.execute(
            select(
                GenerationJobRow.status,
                GenerationJobRow.origin,
                func.count(),
            ).group_by(GenerationJobRow.status, GenerationJobRow.origin)
        )
        for status, origin, count in result.all():
            lines.append(
                f'control_panel_jobs_total{{status="{status}",origin="{origin}"}} {count}'
            )
    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="text/plain; version=0.0.4")
