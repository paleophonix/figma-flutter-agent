"""Job and audit enums for the Discord control plane."""

from __future__ import annotations

from enum import StrEnum


class JobOrigin(StrEnum):
    """Job creation channel."""

    DISCORD = "discord"
    API = "api"


class JobStatus(StrEnum):
    """Lifecycle states for a generation job."""

    CREATED = "created"
    PIPELINE_RUNNING = "pipeline_running"
    PREVIEW_READY = "preview_ready"
    AWAITING_FEEDBACK_COMMENT = "awaiting_feedback_comment"
    FEEDBACK_ISSUE_CREATING = "feedback_issue_creating"
    FEEDBACK_ISSUE_CREATED = "feedback_issue_created"
    ACCEPTED = "accepted"
    MR_CREATING = "mr_creating"
    MR_READY = "mr_ready"
    ISSUE_CLOSED = "issue_closed"
    FAILED = "failed"


class Quality(StrEnum):
    """Discord feedback quality ratings."""

    TOTAL_MESS = "total_mess"
    MAJOR_WRONG = "major_wrong"
    MINOR_WRONG = "minor_wrong"
    GOOD = "good"


QUALITY_LABELS: dict[Quality, str] = {
    Quality.TOTAL_MESS: "полное месиво",
    Quality.MAJOR_WRONG: "значительная часть неверна",
    Quality.MINOR_WRONG: "небольшая мелочь неверна",
    Quality.GOOD: "норм качество",
}

class AutocloseMode(StrEnum):
    """Who may close a feedback issue."""

    DEVELOPER = "developer"
    USER = "user"


FEEDBACK_LABELS: dict[Quality, str] = {
    Quality.TOTAL_MESS: "agent-feedback::total-mess",
    Quality.MAJOR_WRONG: "agent-feedback::major",
    Quality.MINOR_WRONG: "agent-feedback::minor",
    Quality.GOOD: "agent-feedback::good",
}


class IssueKind(StrEnum):
    """Tracker issue category for close routing."""

    BUG = "bug"
    FEAT = "feat"


ISSUE_KIND_LABELS: dict[IssueKind, str] = {
    IssueKind.BUG: "bug",
    IssueKind.FEAT: "feat",
}
