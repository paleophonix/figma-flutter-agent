"""PostHog product/business events for the control panel."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.observability.posthog_transport import (
    CaptureRequest,
    PostHogCaptureSettings,
    capture_policy_from,
    enqueue_capture,
)

TEAM_REQUESTED_GENERATION = "team-requested-generation"
TEAM_OPENED_ISSUE = "team-opened-issue"
AGENT_COMMITTED_CHANGE = "agent-committed-change"
DEV_COMMITTED_CHANGE = "dev-committed-change"
DEV_SUBMITTED_FEEDBACK = "dev-submitted-feedback"

BUSINESS_EVENT_NAMES = frozenset(
    {
        TEAM_REQUESTED_GENERATION,
        TEAM_OPENED_ISSUE,
        AGENT_COMMITTED_CHANGE,
        DEV_COMMITTED_CHANGE,
        DEV_SUBMITTED_FEEDBACK,
    }
)


def resolve_distinct_id(
    *,
    principal: str | None = None,
    discord_user_id: int | None = None,
    job_id: str | None = None,
) -> str:
    """Return a stable PostHog distinct id for control-panel actors."""
    if discord_user_id is not None:
        return f"discord:{discord_user_id}"
    if principal:
        return f"api:{principal}"
    if job_id:
        return f"job:{job_id}"
    return "unknown"


def infer_change_kind(*, commit_message: str, branch: str = "") -> str:
    """Map commit message or branch prefix to ``feat`` or ``fix``."""
    lowered = commit_message.strip().lower()
    if lowered.startswith("fix"):
        return "fix"
    if lowered.startswith("feat"):
        return "feat"
    if branch.startswith("repair/"):
        return "fix"
    return "feat"


def capture_business_event(
    *,
    settings: PostHogCaptureSettings,
    event: str,
    distinct_id: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Queue a business PostHog event (no-op when API key is unset)."""
    if event not in BUSINESS_EVENT_NAMES:
        return
    api_key = settings.posthog_api_key.get_secret_value()
    if not api_key:
        return
    props = dict(properties or {})
    props.setdefault("subject", event.split("-", maxsplit=1)[0])
    enqueue_capture(
        CaptureRequest(
            api_key=api_key,
            host=settings.posthog_host,
            event=event,
            distinct_id=distinct_id,
            properties=props,
            policy=capture_policy_from(settings),
            log_label=f"distinct_id={distinct_id}",
        )
    )
