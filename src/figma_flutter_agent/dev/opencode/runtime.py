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

from figma_flutter_agent.dev.opencode.cli_preflight import OPENCODE_INSTALL_HINT
from figma_flutter_agent.dev.opencode.client import OpenCodeClient, parse_serve_host_port
from figma_flutter_agent.dev.opencode.serve_process import stop_listeners_on_port
from figma_flutter_agent.errors import FigmaFlutterError

SERVE_POLL_INTERVAL_SEC = 0.5
SERVE_START_TIMEOUT_SEC = 30.0

_spawned_process: subprocess.Popen[bytes] | None = None


@dataclass(frozen=True)
class OpenCodeServeStatus:
    """Outcome of ensuring OpenCode serve is reachable."""

    base_url: str
    started_locally: bool
    restarted: bool
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
    openrouter_api_key: str | None = None,
) -> subprocess.Popen[bytes]:
    binary = shutil.which("opencode")
    if binary is None:
        raise FigmaFlutterError(
            f"OpenCode CLI not found on PATH. Install with: {OPENCODE_INSTALL_HINT}"
        )
    cmd = [binary, "serve", "--hostname", hostname, "--port", str(port)]
    env = os.environ.copy()
    if openrouter_api_key:
        env["OPENROUTER_API_KEY"] = openrouter_api_key
    if config_overlay is not None:
        overlay = dict(config_overlay)
        if openrouter_api_key:
            provider = dict(overlay.get("provider") or {})
            openrouter = dict(provider.get("openrouter") or {})
            openrouter["apiKey"] = openrouter_api_key
            provider["openrouter"] = openrouter
            overlay["provider"] = provider
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(overlay, separators=(",", ":"))
        repair_steps = (overlay.get("agent") or {}).get("repair", {}).get("steps")
        logger.info(
            "OpenCode serve overlay: repair agent steps={} bash_denied={}",
            repair_steps,
            ((overlay.get("agent") or {}).get("repair", {}).get("permission") or {}).get("bash")
            == "deny",
        )
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
    openrouter_api_key: str | None = None,
    restart_with_overlay: bool = True,
) -> OpenCodeServeStatus:
    """Ensure ``opencode serve`` responds at ``base_url``.

    When ``restart_with_overlay`` is true and a serve is already listening, the
    listener on the configured port is stopped and respawned so
    ``OPENCODE_CONFIG_CONTENT`` and ``OPENROUTER_API_KEY`` always apply.

    Args:
        base_url: OpenCode server root URL.
        password: Optional basic-auth password.
        username: Basic-auth username.
        timeout_sec: Max wait after local spawn.
        config_overlay: Optional ``OPENCODE_CONFIG_CONTENT`` merged at local spawn.
        openrouter_api_key: Optional OpenRouter key injected into serve env/overlay.
        restart_with_overlay: Kill stale serve before spawn when overlay/key are set.

    Returns:
        Serve status including health payload.

    Raises:
        FigmaFlutterError: When serve cannot be reached or started.
    """
    global _spawned_process  # noqa: PLW0603

    client = OpenCodeClient(base_url=base_url, username=username, password=password)
    health = await _probe_health(client)
    restarted = False
    hostname, port = parse_serve_host_port(base_url)
    needs_fresh_overlay = bool(config_overlay is not None or openrouter_api_key)

    if health is not None and needs_fresh_overlay and restart_with_overlay:
        logger.warning(
            "Restarting OpenCode serve on {}:{} to apply debug_pipeline overlay and API key",
            hostname,
            port,
        )
        if _spawned_process is not None and _spawned_process.poll() is None:
            _spawned_process.terminate()
            _spawned_process = None
        stop_listeners_on_port(port)
        await asyncio.sleep(SERVE_POLL_INTERVAL_SEC)
        restarted = True
        health = None

    if health is not None:
        if needs_fresh_overlay and not restart_with_overlay:
            logger.warning(
                "OpenCode serve already running at {}; overlay not applied because "
                "restart_opencode_serve_with_overlay=false",
                base_url,
            )
        return OpenCodeServeStatus(
            base_url=base_url,
            started_locally=False,
            restarted=False,
            health=health,
        )

    _spawned_process = _spawn_opencode_serve(
        hostname=hostname,
        port=port,
        config_overlay=config_overlay,
        openrouter_api_key=openrouter_api_key,
    )

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        await asyncio.sleep(SERVE_POLL_INTERVAL_SEC)
        health = await _probe_health(client)
        if health is not None:
            return OpenCodeServeStatus(
                base_url=base_url,
                started_locally=True,
                restarted=restarted,
                health=health,
            )

    raise FigmaFlutterError(
        f"OpenCode serve at {base_url} did not become healthy within {timeout_sec:.0f}s. "
        f"Install opencode-ai globally ({OPENCODE_INSTALL_HINT}) or set OPENCODE_BASE_URL "
        "to a running server."
    )
