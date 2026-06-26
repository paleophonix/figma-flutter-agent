"""Ensure a public ngrok tunnel exists for the control panel webhook bind."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from control_panel.config.models import DiscordBotSettings

_NGROK_API_DEFAULT = "http://127.0.0.1:4040"
_TUNNEL_READY_TIMEOUT_SEC = 20.0
_TUNNEL_READY_POLL_SEC = 0.5
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "0.0.0.0", "::1"})


@dataclass(frozen=True)
class NgrokTunnelTarget:
    """Expected public hostname and local webhook port for the control panel."""

    public_host: str
    local_port: int
    domain: str | None


def _env_autostart_enabled() -> bool | None:
    """Return explicit autostart override from ``FIGMA_CP_NGROK_AUTOSTART``."""
    raw = os.getenv("FIGMA_CP_NGROK_AUTOSTART", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return None


def _ngrok_api_base() -> str:
    return os.getenv("FIGMA_CP_NGROK_API_ADDR", _NGROK_API_DEFAULT).rstrip("/")


def parse_webhook_port(webhook_bind: str) -> int:
    """Parse the TCP port from ``host:port`` webhook bind text.

    Args:
        webhook_bind: Value of ``internal.webhook_bind``.

    Returns:
        Local TCP port the control panel listens on.

    Raises:
        ValueError: When the bind string does not contain a valid port.
    """
    _, _, port_text = webhook_bind.rpartition(":")
    if not port_text.isdigit():
        msg = f"Invalid webhook_bind port: {webhook_bind!r}"
        raise ValueError(msg)
    port = int(port_text)
    if port <= 0:
        msg = f"Invalid webhook_bind port: {webhook_bind!r}"
        raise ValueError(msg)
    return port


def _target_from_public_url(public_url: str, *, local_port: int) -> NgrokTunnelTarget | None:
    """Build a tunnel target when ``public_url`` names a public ngrok host."""
    parsed = urlparse(public_url.strip())
    host = (parsed.hostname or "").lower()
    if not host or host in _LOCAL_HOSTS:
        return None
    if not _looks_like_ngrok_host(host):
        return None
    domain_override = os.getenv("FIGMA_CP_NGROK_DOMAIN", "").strip() or None
    domain = domain_override or host
    return NgrokTunnelTarget(public_host=host, local_port=local_port, domain=domain)


def resolve_ngrok_tunnel_target(settings: DiscordBotSettings) -> NgrokTunnelTarget | None:
    """Derive ngrok autostart target from control panel settings.

    Args:
        settings: Loaded control panel settings.

    Returns:
        Tunnel target when autostart should run; otherwise ``None``.
    """
    if _env_autostart_enabled() is False:
        return None
    port = parse_webhook_port(settings.yaml.internal.webhook_bind)
    merged_url = settings.yaml.internal.control_panel_url.strip()
    yaml_url = settings.yaml_control_panel_url.strip()
    candidates: list[str] = []
    for url in (merged_url, yaml_url):
        if url and url not in candidates:
            candidates.append(url)
    for url in candidates:
        target = _target_from_public_url(url, local_port=port)
        if target is not None:
            if url != merged_url and merged_url:
                logger.info(
                    "ngrok autostart uses YAML control_panel_url ({}) because "
                    "FIGMA_CP_INTERNAL_URL overrides runtime URL to {}",
                    target.public_host,
                    merged_url,
                )
            return target
    return None


def _looks_like_ngrok_host(host: str) -> bool:
    return "ngrok" in host


def fetch_ngrok_tunnels(*, api_base: str | None = None) -> list[dict[str, object]]:
    """Return active tunnels from the local ngrok agent API.

    Args:
        api_base: Optional ngrok API origin; defaults to ``FIGMA_CP_NGROK_API_ADDR``.

    Returns:
        Tunnel objects from ``/api/tunnels``. Empty when the agent is not running.
    """
    base = (api_base or _ngrok_api_base()).rstrip("/")
    request = urllib.request.Request(f"{base}/api/tunnels", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return []
    tunnels = payload.get("tunnels")
    if not isinstance(tunnels, list):
        return []
    return [item for item in tunnels if isinstance(item, dict)]


def tunnel_matches_target(tunnel: dict[str, object], *, target: NgrokTunnelTarget) -> bool:
    """Return True when one ngrok tunnel forwards to the expected local port/host."""
    public_url = str(tunnel.get("public_url") or "")
    public_host = (urlparse(public_url).hostname or "").lower()
    if public_host != target.public_host:
        return False
    config = tunnel.get("config")
    if not isinstance(config, dict):
        return False
    addr = str(config.get("addr") or "")
    return addr.endswith(f":{target.local_port}")


def has_active_tunnel(*, target: NgrokTunnelTarget, api_base: str | None = None) -> bool:
    """Return True when ngrok already exposes ``target.public_host`` to the local port."""
    return any(
        tunnel_matches_target(tunnel, target=target) for tunnel in fetch_ngrok_tunnels(api_base=api_base)
    )


def build_ngrok_command(*, target: NgrokTunnelTarget) -> list[str]:
    """Build argv to start ``ngrok http`` for the control panel bind port."""
    executable = shutil.which("ngrok")
    if executable is None:
        msg = "ngrok executable not found on PATH"
        raise FileNotFoundError(msg)
    cmd = [executable, "http", str(target.local_port)]
    if target.domain:
        cmd.extend(["--domain", target.domain])
    return cmd


def start_ngrok_process(*, target: NgrokTunnelTarget) -> subprocess.Popen[str]:
    """Spawn ngrok in the background for one tunnel target.

    Args:
        target: Public hostname and local port to expose.

    Returns:
        Background ``Popen`` handle for the ngrok agent.

    Raises:
        FileNotFoundError: When ``ngrok`` is not available on PATH.
    """
    cmd = build_ngrok_command(target=target)
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    stderr_path = log_dir / "ngrok-autostart.stderr.log"
    logger.info(
        "Starting ngrok for control panel: {} -> localhost:{} (stderr: {})",
        target.public_host,
        target.local_port,
        stderr_path.as_posix(),
    )
    stderr_file = stderr_path.open("ab")
    return subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=stderr_file,
        text=True,
        creationflags=creationflags,
    )


def wait_for_tunnel(
    *,
    target: NgrokTunnelTarget,
    timeout_sec: float = _TUNNEL_READY_TIMEOUT_SEC,
    poll_sec: float = _TUNNEL_READY_POLL_SEC,
) -> bool:
    """Poll the ngrok API until the expected tunnel is registered."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if has_active_tunnel(target=target):
            return True
        time.sleep(poll_sec)
    return False


def ensure_ngrok_tunnel(settings: DiscordBotSettings) -> bool:
    """Start ngrok when the configured public URL requires it and no tunnel is active.

    Args:
        settings: Loaded control panel settings.

    Returns:
        True when a matching tunnel is active after this call.
    """
    target = resolve_ngrok_tunnel_target(settings)
    if target is None:
        logger.info(
            "ngrok autostart skipped (set FIGMA_CP_NGROK_AUTOSTART=1 and a public ngrok "
            "control_panel_url in .control-panel.yml to enable)"
        )
        return False
    logger.info(
        "ngrok autostart check for {} -> localhost:{}",
        target.public_host,
        target.local_port,
    )
    if has_active_tunnel(target=target):
        logger.info(
            "ngrok tunnel already active for {} -> localhost:{}",
            target.public_host,
            target.local_port,
        )
        return True
    if shutil.which("ngrok") is None:
        logger.warning(
            "control_panel_url is public ({}) but ngrok is not on PATH; "
            "install ngrok or set FIGMA_CP_NGROK_AUTOSTART=0 to silence",
            target.public_host,
        )
        return False
    try:
        start_ngrok_process(target=target)
    except FileNotFoundError:
        logger.warning("ngrok executable disappeared before launch")
        return False
    if wait_for_tunnel(target=target):
        logger.info(
            "ngrok tunnel ready for {} -> localhost:{}",
            target.public_host,
            target.local_port,
        )
        return True
    logger.warning(
        "ngrok started but tunnel {} -> localhost:{} did not become ready within {:.0f}s; "
        "see logs/ngrok-autostart.stderr.log",
        target.public_host,
        target.local_port,
        _TUNNEL_READY_TIMEOUT_SEC,
    )
    return False
