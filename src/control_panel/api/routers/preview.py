"""Public HTTP preview proxy routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from control_panel.api.deps import get_settings, get_store
from control_panel.companion.daemon import hash_token
from control_panel.preview.proxy_html import (
    PREVIEW_AUTH_COOKIE,
    parse_preview_cookie,
    preview_cookie_value,
)
from control_panel.preview.request import proxy_preview_request

router = APIRouter(tags=["preview"])

_PREVIEW_PUBLIC_ASSET_BASENAMES = frozenset(
    {"manifest.json", "favicon.png", "version.json", "flutter_service_worker.js"}
)


def is_public_preview_asset(path: str) -> bool:
    """Return True for PWA metadata that may load before the preview auth cookie."""
    trimmed = path.lstrip("/")
    if not trimmed or "/" in trimmed:
        return False
    return trimmed in _PREVIEW_PUBLIC_ASSET_BASENAMES


def _validate_preview_token(job_token_hash: str | None, token: str) -> None:
    if not job_token_hash or not token:
        raise HTTPException(status_code=401, detail="unauthorized")
    if hash_token(token) != job_token_hash:
        raise HTTPException(status_code=401, detail="unauthorized")


def _resolve_preview_mode(request: Request, *, default: str = "fixed") -> str:
    """Resolve preview mode from query params or auth cookie."""
    mode = request.query_params.get("mode", default)
    if mode in {"fixed", "adaptive"}:
        return mode
    parsed = parse_preview_cookie(request.cookies.get(PREVIEW_AUTH_COOKIE, ""))
    if parsed is not None and parsed[1] in {"fixed", "adaptive"}:
        return parsed[1]
    return default


def _resolve_preview_auth(
    request: Request,
    *,
    job_id: str,
    job_token_hash: str | None,
) -> tuple[str, str]:
    """Resolve preview token and mode from query params or preview cookie."""
    token = request.query_params.get("token", "")
    mode = request.query_params.get("mode", "fixed")
    if token:
        _validate_preview_token(job_token_hash, token)
        if mode not in {"fixed", "adaptive"}:
            raise HTTPException(status_code=400, detail="invalid_mode")
        return token, mode

    parsed = parse_preview_cookie(request.cookies.get(PREVIEW_AUTH_COOKIE, ""))
    if parsed is None or parsed[0] != job_id:
        raise HTTPException(status_code=401, detail="unauthorized")
    cookie_job_id, cookie_mode, cookie_token = parsed
    _ = cookie_job_id
    _validate_preview_token(job_token_hash, cookie_token)
    mode = request.query_params.get("mode", cookie_mode)
    if mode not in {"fixed", "adaptive"}:
        raise HTTPException(status_code=400, detail="invalid_mode")
    return cookie_token, mode


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
    settings = get_settings(request)
    job = await store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")

    if is_public_preview_asset(path):
        mode = _resolve_preview_mode(request)
        token = ""
    else:
        token, mode = _resolve_preview_auth(
            request,
            job_id=job_id,
            job_token_hash=job.preview_token_hash,
        )

    status, response_headers, content = await proxy_preview_request(
        request,
        store,
        job_id=job_id,
        mode=mode,
        path=path,
        preview_config=settings.yaml.preview,
    )
    content_type = response_headers.get("content-type", "")

    if request.method == "HEAD":
        response: Response = Response(status_code=status, headers=response_headers)
    elif "text/event-stream" in content_type:
        return StreamingResponse(
            iter([content]),
            status_code=status,
            headers=response_headers,
        )
    else:
        response = Response(
            content=content,
            status_code=status,
            headers=response_headers,
        )

    if request.query_params.get("token"):
        response.set_cookie(
            key=PREVIEW_AUTH_COOKIE,
            value=preview_cookie_value(job_id=job_id, mode=mode, token=token),
            httponly=True,
            samesite="lax",
            max_age=3600,
            path="/",
        )
    return response
