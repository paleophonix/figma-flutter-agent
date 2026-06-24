"""Prometheus HTTP request metrics middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from figma_flutter_agent.observability.prometheus_metrics import inc_http_request

_SKIP_PATHS = frozenset({"/health", "/ready", "/metrics"})


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Count control panel HTTP requests by route template and status."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)
        response = await call_next(request)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        inc_http_request(request.method, route_path, response.status_code)
        return response
