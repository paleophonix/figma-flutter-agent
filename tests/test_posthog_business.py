"""Unit tests for PostHog business event capture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from figma_flutter_agent.observability.posthog_business import (
    AGENT_COMMITTED_CHANGE,
    BUSINESS_EVENT_NAMES,
    DEV_COMMITTED_CHANGE,
    TEAM_REQUESTED_GENERATION,
    capture_business_event,
    infer_change_kind,
    resolve_distinct_id,
)
from figma_flutter_agent.observability.posthog_transport import CaptureRequest


@pytest.fixture
def posthog_settings() -> MagicMock:
    settings = MagicMock()
    settings.posthog_api_key = SecretStr("phc_test")
    settings.posthog_host = "https://us.i.posthog.com"
    settings.posthog_capture_max_attempts = 3
    settings.posthog_capture_timeout_sec = 8.0
    settings.posthog_capture_retry_base_sec = 0.75
    return settings


def test_business_event_catalog_has_five_events() -> None:
    assert len(BUSINESS_EVENT_NAMES) == 5
    assert TEAM_REQUESTED_GENERATION in BUSINESS_EVENT_NAMES
    assert DEV_COMMITTED_CHANGE in BUSINESS_EVENT_NAMES


def test_resolve_distinct_id_prefers_discord() -> None:
    assert resolve_distinct_id(discord_user_id=42, principal="alice") == "discord:42"


def test_infer_change_kind_from_branch() -> None:
    assert infer_change_kind(commit_message="", branch="repair/abc") == "fix"
    assert infer_change_kind(commit_message="feat: layout", branch="figma/foo") == "feat"


@patch("figma_flutter_agent.observability.posthog_business.enqueue_capture")
def test_capture_business_event_queues_payload(
    enqueue_mock: MagicMock,
    posthog_settings: MagicMock,
) -> None:
    capture_business_event(
        settings=posthog_settings,
        event=AGENT_COMMITTED_CHANGE,
        distinct_id="discord:1",
        properties={"job_id": "abc", "change_kind": "feat"},
    )
    enqueue_mock.assert_called_once()
    request: CaptureRequest = enqueue_mock.call_args.args[0]
    assert request.event == AGENT_COMMITTED_CHANGE
    assert request.distinct_id == "discord:1"
    assert request.properties["job_id"] == "abc"
    assert request.properties["subject"] == "agent"


@patch("figma_flutter_agent.observability.posthog_business.enqueue_capture")
def test_capture_skips_without_api_key(
    enqueue_mock: MagicMock,
    posthog_settings: MagicMock,
) -> None:
    posthog_settings.posthog_api_key = SecretStr("")
    capture_business_event(
        settings=posthog_settings,
        event=TEAM_REQUESTED_GENERATION,
        distinct_id="api:alice",
        properties={"job_id": "x"},
    )
    enqueue_mock.assert_not_called()


@patch("figma_flutter_agent.observability.posthog_business.enqueue_capture")
def test_capture_skips_unknown_event_name(
    enqueue_mock: MagicMock,
    posthog_settings: MagicMock,
) -> None:
    capture_business_event(
        settings=posthog_settings,
        event="team-made-pizza",
        distinct_id="discord:1",
        properties={},
    )
    enqueue_mock.assert_not_called()
