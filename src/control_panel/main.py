"""Uvicorn entrypoint for the control panel API and optional Discord bot."""

from __future__ import annotations

import warnings

import uvicorn

from control_panel.api.app import parse_bind
from control_panel.config import load_discord_bot_settings
from control_panel.services.ngrok import ensure_ngrok_tunnel
from figma_flutter_agent.logging_setup import configure_logging


def main() -> None:
    """Run FastAPI with optional embedded Discord bot."""
    configure_logging(verbose=False)
    settings = load_discord_bot_settings(require_discord_token=False)
    ensure_ngrok_tunnel(settings)
    host, port = parse_bind(settings.yaml.internal.webhook_bind)
    uvicorn.run(
        "control_panel.api.app:app",
        host=host,
        port=port,
        factory=False,
    )


def legacy_main() -> None:
    """Deprecated alias for ``figma-flutter-discord``."""
    warnings.warn(
        "figma-flutter-discord is deprecated; use figma-flutter-control-panel",
        DeprecationWarning,
        stacklevel=2,
    )
    main()


if __name__ == "__main__":
    main()
