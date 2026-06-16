"""Uvicorn entrypoint for the control plane API and Discord bot."""

from __future__ import annotations

import uvicorn

from discord_bot.api.app import parse_bind
from discord_bot.config import load_discord_bot_settings
from figma_flutter_agent.logging_setup import configure_logging


def main() -> None:
    """Run FastAPI with embedded Discord bot."""
    configure_logging(verbose=False)
    settings = load_discord_bot_settings()
    host, port = parse_bind(settings.yaml.internal.webhook_bind)
    uvicorn.run(
        "discord_bot.api.app:app",
        host=host,
        port=port,
        factory=False,
    )


if __name__ == "__main__":
    main()
