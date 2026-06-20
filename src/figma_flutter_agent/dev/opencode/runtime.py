"""Auto-start and health-check local ``opencode serve``."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger

from figma_flutter_agent.dev.opencode.client import OpenCodeClient, parse_serve_host_port
from figma_flutter_agent.errors import FigmaFlutterError

SERVE_POLL_INTERVAL_SEC = 0.5
SERVE_START_TIMEOUT_SEC = 30.0

_spawned_process: subprocess.Popen[bytes] | None = None


@dataclass(frozen=True)
class OpenCodeServeStatus:
    """Outcome of ensuring OpenCode serve is reachable."""

    base_url: str
    started_locally: bool
    health: dict[str, object]


async def _probe_health(client: OpenCodeClient) -> dict[str, object] | None:
    try:
        return await client.health()
    except Exception:
        return None


def _spawn_opencode_serve(
    *,
    hostname: str,
    port: int,
    config_overlay: dict[str, Any] | None = None,
) -> subprocess.Popen[bytes]:
    binary = shutil.which("opencode")
    if binary is None:
        raise FigmaFlutterError(
            "OpenCode CLI not found on PATH. Install with: npm install -g opencode-ai"
        )
    cmd = [binary, "serve", "--hostname", hostname, "--port", str(port)]
    env = os.environ.copy()
    if config_overlay is not None:
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config_overlay, separators=(",", ":"))
        logger.info("OpenCode serve overlay: effort/model agents synced from debug_pipeline")
    logger.info("Starting OpenCode serve: {}", " ".join(cmd))
    kwargs: dict[str, object] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    kwargs["env"] = env
    return subprocess.Popen(cmd, **kwargs)  # type: ignore[call-overload, arg-type]


async def ensure_opencode_serve(
    *,
    base_url: str,
    password: str = "",
    username: str = "opencode",
    timeout_sec: float = SERVE_START_TIMEOUT_SEC,
    config_overlay: dict[str, Any] | None = None,
) -> OpenCodeServeStatus:
    """Ensure ``opencode serve`` responds at ``base_url``.

    Args:
        base_url: OpenCode server root URL.
        password: Optional basic-auth password.
        username: Basic-auth username.
        timeout_sec: Max wait after local spawn.
        config_overlay: Optional ``OPENCODE_CONFIG_CONTENT`` merged at local spawn.

    Returns:
        Serve status including health payload.

    Raises:
        FigmaFlutterError: When serve cannot be reached or started.
    """
    global _spawned_process  # noqa: PLW0603

    client = OpenCodeClient(base_url=base_url, username=username, password=password)
    health = await _probe_health(client)
    if health is not None:
        if config_overlay is not None:
            logger.warning(
                "OpenCode serve already running at {}; debug_pipeline overlay applies only "
                "to per-message model/reasoning options (restart serve to merge agent config)",
                base_url,
            )
        return OpenCodeServeStatus(base_url=base_url, started_locally=False, health=health)

    hostname, port = parse_serve_host_port(base_url)
    if _spawned_process is None or _spawned_process.poll() is not None:
        _spawned_process = _spawn_opencode_serve(
            hostname=hostname,
            port=port,
            config_overlay=config_overlay,
        )

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        await asyncio.sleep(SERVE_POLL_INTERVAL_SEC)
        health = await _probe_health(client)
        if health is not None:
            return OpenCodeServeStatus(base_url=base_url, started_locally=True, health=health)

    raise FigmaFlutterError(
        f"OpenCode serve at {base_url} did not become healthy within {timeout_sec:.0f}s. "
        "Install opencode-ai globally or set OPENCODE_BASE_URL to a running server."
    )
