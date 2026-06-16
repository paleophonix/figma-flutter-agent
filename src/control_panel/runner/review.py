"""Review text for GitLab feedback issues."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FeedbackReview(BaseModel):
    """Structured review payload for GitLab issues."""

    title: str = Field(min_length=8, max_length=120)
    body: str = Field(min_length=20)


async def generate_feedback_review(
    *,
    job_id: str,
    figma_url: str,
    quality_label: str,
    warnings: list[str],
    feature_slug: str | None,
) -> FeedbackReview:
    """Build issue title and body from pipeline warnings and user rating."""
    warning_block = "\n".join(f"- {item}" for item in warnings[:30]) or "- (none)"
    body = (
        f"## Model review\n\n"
        f"Quality rating: **{quality_label}**\n"
        f"Feature: `{feature_slug or 'unknown'}`\n"
        f"Figma: {figma_url}\n\n"
        f"## Pipeline warnings\n{warning_block}\n"
    )
    return FeedbackReview(
        title=f"[Agent feedback] Layout issues for job {job_id[:8]}",
        body=body,
    )
