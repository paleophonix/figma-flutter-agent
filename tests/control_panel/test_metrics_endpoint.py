"""Control panel metrics exposition tests."""

from __future__ import annotations

from figma_flutter_agent.observability.prometheus_metrics import (
    metrics_content_type,
    refresh_jobs_snapshot,
    refresh_repair_jobs_snapshot,
    render_metrics,
    set_component_ready,
)


def test_metrics_content_type_is_prometheus() -> None:
    assert "text/plain" in metrics_content_type()


def test_control_panel_snapshot_gauges_in_exposition() -> None:
    set_component_ready("postgres", True)
    set_component_ready("redis", True)
    refresh_jobs_snapshot({("preview_ready", "api"): 3})
    refresh_repair_jobs_snapshot({"queued": 1})
    body = render_metrics().decode("utf-8")
    assert "control_panel_jobs_snapshot" in body
    assert "control_panel_repair_jobs_snapshot" in body
    assert 'control_panel_ready{component="postgres"} 1.0' in body
