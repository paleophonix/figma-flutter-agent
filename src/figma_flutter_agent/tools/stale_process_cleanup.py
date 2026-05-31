"""Terminate orphaned agent-owned subprocesses left after killed terminals."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence

from loguru import logger

_STALE_IMAGE_BASENAMES = (
    "ast_compiler.exe",
    "ast_compiler-linux",
    "ast_compiler-macos",
)


def _cleanup_disabled() -> bool:
    raw = os.environ.get("FIGMA_FLUTTER_SKIP_STALE_CLEANUP", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _kill_pids_windows(pids: Sequence[int]) -> int:
    killed = 0
    current = os.getpid()
    for pid in sorted(set(pids)):
        if pid <= 0 or pid == current:
            continue
        proc = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            killed += 1
    return killed


def _collect_stale_pids_windows() -> list[int]:
    names_clause = " -or ".join(f"$_.Name -eq '{name}'" for name in _STALE_IMAGE_BASENAMES)
    script = (
        f"$mine = {os.getpid()}; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { "
        f"$_.ProcessId -ne $mine -and ({names_clause} "
        "-or ($_.Name -eq 'dart.exe' -and $_.CommandLine -match 'ast_compiler|dart_ast_sidecar')) "
        "} | Select-Object -ExpandProperty ProcessId"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    pids: list[int] = []
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.isdigit():
            pids.append(int(stripped))
    return pids


def _kill_image_names_windows() -> int:
    killed = 0
    for name in _STALE_IMAGE_BASENAMES:
        proc = subprocess.run(
            ["taskkill", "/F", "/IM", name],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            killed += 1
    return killed


def _cleanup_windows() -> int:
    killed = _kill_pids_windows(_collect_stale_pids_windows())
    killed += _kill_image_names_windows()
    return killed


def _cleanup_unix() -> int:
    killed = 0
    for pattern in (
        "ast_compiler",
        "dart_ast_sidecar/bin/ast_compiler.dart",
    ):
        proc = subprocess.run(
            ["pkill", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            killed += 1
    return killed


def cleanup_stale_agent_processes(*, log: bool = True) -> int:
    """Kill hung AST sidecar (and related ``dart``) processes from prior agent runs.

    Skipped when ``FIGMA_FLUTTER_SKIP_STALE_CLEANUP`` is set to a truthy value.
    Does not terminate ``flutter run`` or other interactive ``figma-flutter`` sessions.
    """
    if _cleanup_disabled():
        return 0
    if sys.platform == "win32":
        killed = _cleanup_windows()
    else:
        killed = _cleanup_unix()
    if log and killed:
        logger.info(
            "Terminated {} stale agent subprocess group(s) from a prior run",
            killed,
        )
    return killed
