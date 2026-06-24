"""Shared HTTP preview proxy request handling."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request

from control_panel.config.models import PreviewConfig
from control_panel.db.store import JobStore
from control_panel.preview.proxy_html import inject_preview_base_href, rewrite_preview_root_paths
from control_panel.preview.release import read_release_preview_file, release_preview_enabled
from control_panel.preview.serve import ensure_flutter_preview_server
from figma_flutter_agent.dev.preview_size import CHROME_PREVIEW_WEB_HOST


async def proxy_preview_request(
    request: Request,
    store: JobStore,
    *,
    job_id: str,
    mode: str,
    path: str = "",
    preview_config: PreviewConfig,
) -> tuple[int, dict[str, str], bytes]:
    """Proxy one preview HTTP request to the colocated Flutter web-server.

    Args:
        request: Incoming FastAPI request.
        store: Job persistence store.
        job_id: Generation job id.
        mode: ``fixed`` or ``adaptive``.
        path: Upstream path relative to the Flutter web root.

    Returns:
        Tuple of status code, response headers, and body bytes.

    Raises:
        HTTPException: When the job is missing or preview cannot start.
    """
    job = await store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")

    project_dir = Path(job.project_dir)
    if release_preview_enabled(preview_config):
        release_response = read_release_preview_file(project_dir, mode, path)
        if release_response is not None:
            status, response_headers, content = release_response
            content_type = response_headers.get("content-type", "")
            if (
                request.method == "GET"
                and path == ""
                and status == 200
                and "text/html" in content_type
            ):
                content = inject_preview_base_href(content, job_id=job_id)
                content = rewrite_preview_root_paths(content, job_id=job_id)
            return status, response_headers, content

    try:
        port = ensure_flutter_preview_server(project_dir=project_dir, mode=mode)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    upstream_path = flutter_preview_upstream_path(job_id=job_id, path=path)
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

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in {"content-length", "transfer-encoding"}
    }
    content = upstream.content
    content_type = upstream.headers.get("content-type", "")
    if request.method == "GET" and path == "" and "text/html" in content_type:
        content = inject_preview_base_href(content, job_id=job_id)
        content = rewrite_preview_root_paths(content, job_id=job_id)
    return upstream.status_code, response_headers, content


def preview_public_prefix(job_id: str) -> str:
    """Return the public URL prefix for one preview job."""
    return f"/preview/{quote(job_id, safe='')}"


def flutter_preview_upstream_path(*, job_id: str, path: str) -> str:
    """Map a public proxy path to the Flutter web-server path.

    ``flutter run --base-href=/preview/{job_id}/`` serves HTML and assets under that
    prefix on the local web-server device, not at ``/``.
    """
    prefix = preview_public_prefix(job_id)
    trimmed = path.lstrip("/")
    if trimmed:
        return f"{prefix}/{trimmed}"
    return f"{prefix}/"
