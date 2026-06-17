"""Control plane API middleware."""

from control_panel.api.middleware.prometheus import PrometheusMiddleware

__all__ = ["PrometheusMiddleware"]
