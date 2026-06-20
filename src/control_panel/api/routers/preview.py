"""Public HTTP preview proxy routes."""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from control_panel.api.deps import get_store
from control_panel.companion.daemon import hash_token
from control_panel.preview.serve import ensure_flutter_preview_server
from figma_flutter_agent.dev.preview_size import CHROME_PREVIEW_WEB_HOST

router = APIRouter(tags=["preview"])


def _validate_preview_token(job_token_hash: str | None, token: str) -> None:
    if not job_token_hash or not token:
        raise HTTPException(status_code=401, detail="unauthorized")
    if hash_token(token) != job_token_hash:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/preview/{job_id}")
@router.api_route(
    "/preview/{job_id}/{path:path}",
    methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def preview_proxy(
    request: Request,
    job_id: str,
    path: str = "",
) -> Response:
    """Proxy HTTP requests to the colocated Flutter web-server preview."""
    store = get_store(request)
    job = await store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")

    token = request.query_params.get("token", "")
    _validate_preview_token(job.preview_token_hash, token)
    mode = request.query_params.get("mode", "fixed")
    if mode not in {"fixed", "adaptive"}:
        raise HTTPException(status_code=400, detail="invalid_mode")

    project_dir = Path(job.project_dir)
    try:
        port = ensure_flutter_preview_server(project_dir=project_dir, mode=mode)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    upstream_path = f"/{path}" if path else "/"
    query_items = [
        (key, value)
        for key, value in request.query_params.multi_items()
        if key not in {"token", "mode"}
    ]
    upstream_url = f"http://{CHROME_PREVIEW_WEB_HOST}:{port}{upstream_path}"
    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        upstream = await client.request(
            request.method,
            upstream_url,
            params=query_items,
            headers=headers,
            content=body,
        )
    if request.method == "HEAD":
        return Response(status_code=upstream.status_code, headers=dict(upstream.headers))
    if "text/event-stream" in upstream.headers.get("content-type", ""):
        return StreamingResponse(
            upstream.aiter_bytes(),
            status_code=upstream.status_code,
            headers=dict(upstream.headers),
        )
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=dict(upstream.headers),
    )
