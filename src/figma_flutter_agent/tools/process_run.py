"""Subprocess helpers with timeouts so pipeline stages cannot hang indefinitely."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from loguru import logger

# Keep in sync with repair / write / golden capture expectations.
DART_FORMAT_TIMEOUT_SEC = 90.0
FLUTTER_PUB_GET_TIMEOUT_SEC = 180.0
DART_ANALYZE_TIMEOUT_SEC = 120.0
FLUTTER_TEST_TIMEOUT_SEC = 600.0
BUILD_RUNNER_TIMEOUT_SEC = 600.0
DOCKER_COMPOSE_TIMEOUT_SEC = 900.0
_TERMINATE_WAIT_SEC = 5.0


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    """Force-stop a subprocess and any children (Windows ``dart`` spawns helpers)."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return
    proc.terminate()


def run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path,
    label: str,
    timeout_sec: float,
    log: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a CLI command with a hard timeout and process-tree termination.

    Args:
        command: argv for the child process.
        cwd: Working directory.
        label: Short description for logs (for example ``flutter pub get``).
        timeout_sec: Maximum wall time in seconds.
        log: When False, skip start/finish log lines (batch callers log progress).

    Returns:
        Completed process (non-zero exit codes are not raised).

    Raises:
        subprocess.TimeoutExpired: When the command exceeds ``timeout_sec``.
    """
    argv = list(command)
    if log:
        logger.info("Running {} (timeout {:.0f}s)", label, timeout_sec)
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        logger.error("{} timed out after {:.0f}s; killing process tree", label, timeout_sec)
        _terminate_process_tree(proc)
        try:
            stdout, stderr = proc.communicate(timeout=_TERMINATE_WAIT_SEC)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=_TERMINATE_WAIT_SEC)
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout_sec, output=stdout, stderr=stderr) from exc
    if log:
        logger.info("{} finished with exit code {}", label, proc.returncode)
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)
