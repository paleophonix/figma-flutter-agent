"""Tests for Grafana Loki log shipping."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
from pydantic import SecretStr

from figma_flutter_agent.config import Settings
from figma_flutter_agent.observability import loki_sink


def _settings_with_loki() -> Settings:
    return Settings.model_construct(
        loki_url="https://logs.example.com",
        loki_user="123456",
        loki_api_key=SecretStr("glc_test"),
        loki_labels="env=test",
        loki_batch_size=2,
        loki_flush_interval_sec=0.05,
        loki_push_max_attempts=3,
        loki_push_timeout_sec=5.0,
        loki_push_retry_base_sec=0.1,
    )


def test_normalize_loki_push_url_appends_suffix() -> None:
    assert (
        loki_sink.normalize_loki_push_url("https://logs.example.com")
        == "https://logs.example.com/loki/api/v1/push"
    )
    assert (
        loki_sink.normalize_loki_push_url("https://logs.example.com/loki/api/v1/push")
        == "https://logs.example.com/loki/api/v1/push"
    )


def test_parse_loki_labels_merges_defaults() -> None:
    labels = loki_sink.parse_loki_labels("env=dev,team=celestial")
    assert labels["service"] == "figma-flutter-agent"
    assert labels["env"] == "dev"
    assert labels["team"] == "celestial"


def test_loki_push_enabled_requires_url() -> None:
    assert not loki_sink.loki_push_enabled(Settings.model_construct(loki_url=""))
    assert loki_sink.loki_push_enabled(_settings_with_loki())


def test_loki_push_disabled_when_flag_off() -> None:
    settings = Settings.model_construct(
        loki_enabled=False,
        loki_url="https://logs.example.com",
    )
    assert not loki_sink.loki_push_enabled(settings)


def test_build_auth_uses_bearer_without_user() -> None:
    settings = Settings.model_construct(
        loki_user="",
        loki_api_key=SecretStr("token-only"),
    )
    auth = loki_sink._build_auth(settings)
    assert isinstance(auth, loki_sink._BearerAuth)


def test_push_batch_uses_basic_auth_and_json_payload() -> None:
    settings = _settings_with_loki()
    sink = loki_sink.LokiSink(settings)
    batch = [
        loki_sink._LogEntry(ts_ns="1", line='{"message":"hello"}'),
        loki_sink._LogEntry(ts_ns="2", line='{"message":"world"}'),
    ]

    with patch.object(loki_sink.httpx, "post") as mock_post:
        mock_post.return_value = httpx.Response(204)
        sink._push_batch(batch)

    mock_post.assert_called_once()
    kwargs = mock_post.call_args.kwargs
    assert kwargs["auth"] is not None
    payload = kwargs["json"]
    assert payload["streams"][0]["stream"]["env"] == "test"
    assert payload["streams"][0]["values"] == [
        ["1", '{"message":"hello"}'],
        ["2", '{"message":"world"}'],
    ]
    sink.close()


def test_push_batch_retries_on_timeout() -> None:
    settings = _settings_with_loki()
    sink = loki_sink.LokiSink(settings)
    batch = [loki_sink._LogEntry(ts_ns="1", line='{"message":"retry"}')]

    with (
        patch.object(loki_sink.httpx, "post", side_effect=httpx.ReadTimeout("timed out")),
        patch.object(loki_sink.time, "sleep"),
        patch.object(loki_sink.logger, "warning") as mock_warning,
    ):
        sink._push_batch(batch)

    mock_warning.assert_called_once()
    assert "gave up" in str(mock_warning.call_args)
    sink.close()


def test_attach_loki_sink_noop_without_url() -> None:
    settings = Settings.model_construct(loki_url="")
    assert loki_sink.attach_loki_sink(settings=settings, level="INFO") is None


def test_format_log_line_includes_bound_extra() -> None:
    record = {
        "level": MagicMock(name="INFO"),
        "name": "figma_flutter_agent.pipeline",
        "function": "run_pipeline",
        "line": 196,
        "message": "Pipeline run started",
        "extra": {"run_id": "abc123", "stage": "fetch"},
    }
    record["level"].name = "INFO"
    line = loki_sink._format_log_line(record)
    payload = json.loads(line)
    assert payload["message"] == "Pipeline run started"
    assert payload["extra"]["run_id"] == "abc123"
    assert payload["extra"]["stage"] == "fetch"
