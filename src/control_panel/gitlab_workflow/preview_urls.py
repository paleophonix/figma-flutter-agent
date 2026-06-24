"""HTTP preview URL helpers for GitLab Issue workflow."""

from __future__ import annotations

from urllib.parse import quote

from control_panel.config import DiscordBotSettings


def build_http_preview_url(
    settings: DiscordBotSettings,
    *,
    job_id: str,
    token: str,
    mode: str = "fixed",
) -> str:
    """Build a public control-panel preview URL for one job."""
    base = settings.yaml.internal.control_panel_url.rstrip("/")
    return (
        f"{base}/preview/{quote(job_id, safe='')}"
        f"?mode={quote(mode, safe='')}&token={quote(token, safe='')}"
    )
