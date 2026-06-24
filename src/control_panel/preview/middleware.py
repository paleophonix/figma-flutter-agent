"""Middleware that proxies Flutter web root assets using preview auth cookies."""

from __future__ import annotations

import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from control_panel.preview.proxy_html import PREVIEW_AUTH_COOKIE, parse_preview_cookie
from control_panel.preview.request import proxy_preview_request

_PREVIEW_ROOT_ASSET_RE = re.compile(
    r"^/(?:flutter_bootstrap\.js|flutter\.js|main\.dart\.js|manifest\.json|favicon\.png|version\.json|assets/.*|canvaskit/.*)$"
)


class PreviewRootAssetMiddleware(BaseHTTPMiddleware):
    """Proxy Flutter web assets requested from site root after preview auth."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in {"GET", "HEAD"}:
            return await call_next(request)
        path = request.url.path
        if path.startswith("/preview/") or not _PREVIEW_ROOT_ASSET_RE.match(path):
            return await call_next(request)

        parsed = parse_preview_cookie(request.cookies.get(PREVIEW_AUTH_COOKIE, ""))
        if parsed is None:
            return await call_next(request)

        job_id, mode, _token = parsed
        store = request.app.state.store
        settings = request.app.state.settings
        asset_path = path.lstrip("/")
        status, headers, content = await proxy_preview_request(
            request,
            store,
            job_id=job_id,
            mode=mode,
            path=asset_path,
            preview_config=settings.yaml.preview,
        )
        if request.method == "HEAD":
            return Response(status_code=status, headers=headers)
        return Response(content=content, status_code=status, headers=headers)
