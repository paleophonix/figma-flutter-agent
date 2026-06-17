"""Unit tests for Prometheus metrics helpers."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from figma_flutter_agent.observability import log_stage
from figma_flutter_agent.observability.prometheus_metrics import (
    ARQ_JOBS_TOTAL,
    CONTROL_PANEL_HTTP_REQUESTS,
    FORBIDDEN_LABEL_NAMES,
    PIPELINE_STAGE_DURATION,
    assert_low_cardinality_labels,
    observe_figma_request,
    observe_pipeline_stage,
    record_llm_request,
    refresh_jobs_snapshot,
    render_metrics,
    track_arq_job,
)


def test_render_metrics_exposes_pipeline_stage() -> None:
    observe_pipeline_stage("fetch", 0.5, outcome="success")
    body = render_metrics().decode("utf-8")
    assert "pipeline_stage_duration_seconds" in body


def test_figma_endpoint_normalization() -> None:
    observe_figma_request("/v1/files/abc123/nodes", 200, 0.2)
    body = render_metrics().decode("utf-8")
    assert 'endpoint="/v1/files"' in body
    assert "figma_api_requests_total" in body


def test_record_llm_request_skips_empty_span() -> None:
    before = render_metrics()
    record_llm_request("", latency_sec=1.0, is_error=False)
    after = render_metrics()
    assert before == after


def test_record_llm_request_increments_counter() -> None:
    record_llm_request("generate", latency_sec=0.3, is_error=False)
    body = render_metrics().decode("utf-8")
    assert 'llm_requests_total{outcome="success",span_name="generate"}' in body


def test_track_arq_job_records_success() -> None:
    with track_arq_job("run_generation_job"):
        pass
    body = render_metrics().decode("utf-8")
    assert 'arq_jobs_total{outcome="success",task="run_generation_job"}' in body


def test_track_arq_job_records_failure() -> None:
    with pytest.raises(RuntimeError), track_arq_job("publish_job"):
        raise RuntimeError("boom")
    body = render_metrics().decode("utf-8")
    assert 'arq_jobs_total{outcome="failed",task="publish_job"}' in body


def test_refresh_jobs_snapshot_zeros_stale_labels() -> None:
    refresh_jobs_snapshot({("failed", "api"): 2})
    refresh_jobs_snapshot({("preview_ready", "discord"): 1})
    body = render_metrics().decode("utf-8")
    assert 'control_panel_jobs_snapshot{origin="discord",status="preview_ready"} 1.0' in body
    assert 'control_panel_jobs_snapshot{origin="api",status="failed"} 0.0' in body


def test_log_stage_observes_histogram() -> None:
    class _Log:
        def bind(self, **_kwargs: object) -> _Log:
            return self

        def info(self, *_args: object, **_kwargs: object) -> None:
            return None

        def error(self, *_args: object, **_kwargs: object) -> None:
            return None

        def exception(self, *_args: object, **_kwargs: object) -> None:
            return None

    with patch(
        "figma_flutter_agent.observability.prometheus_metrics.observe_pipeline_stage"
    ) as mock_observe:
        with log_stage(_Log(), "parse"):
            time.sleep(0.01)
        mock_observe.assert_called_once()
        assert mock_observe.call_args.args[0] == "parse"
        assert mock_observe.call_args.kwargs["outcome"] == "success"


def test_forbidden_labels_not_used_on_p0_metrics() -> None:
    for metric in (
        ARQ_JOBS_TOTAL,
        CONTROL_PANEL_HTTP_REQUESTS,
        PIPELINE_STAGE_DURATION,
    ):
        assert_low_cardinality_labels(metric)
    assert "job_id" in FORBIDDEN_LABEL_NAMES
