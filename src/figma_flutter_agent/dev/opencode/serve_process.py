"""Find and stop a local OpenCode ``serve`` listener."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable

from loguru import logger


def pids_listening_on_port(port: int) -> list[int]:
    """Return process ids listening on ``port`` on the local machine.

    Args:
        port: TCP port number.

    Returns:
        Distinct PIDs bound to LISTENING sockets on that port.
    """
    if port <= 0:
        return []
    if sys.platform == "win32":
        return _pids_listening_on_port_windows(port)
    return _pids_listening_on_port_unix(port)


def stop_listeners_on_port(port: int, *, exclude_pids: Iterable[int] = ()) -> list[int]:
    """Terminate processes listening on ``port``.

    Args:
        port: TCP port number.
        exclude_pids: PIDs that must not be killed (for example the current process).

    Returns:
        PIDs that were signalled for termination.
    """
    excluded = {int(pid) for pid in exclude_pids}
    stopped: list[int] = []
    for pid in pids_listening_on_port(port):
        if pid in excluded:
            continue
        if _terminate_pid(pid):
            stopped.append(pid)
    if stopped:
        logger.info("Stopped OpenCode serve listener(s) on port {}: {}", port, stopped)
    return stopped


def _pids_listening_on_port_windows(port: int) -> list[int]:
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        check=False,
    )
    needle = f":{port}"
    pids: list[int] = []
    for line in result.stdout.splitlines():
        if "LISTENING" not in line or needle not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pids.append(int(parts[-1]))
        except ValueError:
            continue
    return list(dict.fromkeys(pids))


def _pids_listening_on_port_unix(port: int) -> list[int]:
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return list(dict.fromkeys(pids))


def _terminate_pid(pid: int) -> bool:
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                check=False,
            )
        else:
            subprocess.run(["kill", "-TERM", str(pid)], capture_output=True, check=False)
    except OSError:
        logger.exception("Failed to terminate pid {}", pid)
        return False
    return True
