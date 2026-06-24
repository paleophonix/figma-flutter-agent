"""Post lifecycle events to the control panel internal API."""

from __future__ import annotations

import httpx

from control_panel.config import DiscordBotSettings


async def post_job_event(
    settings: DiscordBotSettings,
    *,
    job_id: str,
    event: str,
    error_message: str | None = None,
) -> None:
    """Notify the API process about a worker lifecycle event."""
    secret = settings.yaml.internal.callback_secret
    if not secret:
        return
    url = settings.yaml.internal.control_panel_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{url}/internal/jobs/{job_id}/events",
            json={"event": event, "error_message": error_message},
            headers={"X-Internal-Secret": secret},
        )
        response.raise_for_status()
