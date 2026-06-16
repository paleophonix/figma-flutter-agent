"""CLI entrypoint for the ARQ worker."""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """Run the ARQ worker process."""
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "arq", "discord_bot.workers.settings.WorkerSettings"],
        )
    )


if __name__ == "__main__":
    main()
