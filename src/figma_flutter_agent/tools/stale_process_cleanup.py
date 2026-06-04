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

_AGENT_CMD_MARKERS = ("figma-flutter", "figma_flutter_agent")


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


def _run_powershell(script: str) -> str:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout or ""


def _active_figma_flutter_pids_windows() -> set[int]:
    """PIDs of other live ``figma-flutter`` / agent Python sessions on this machine."""
    markers = "|".join(_AGENT_CMD_MARKERS)
    script = (
        f"$mine = {os.getpid()}; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { "
        f"$_.ProcessId -ne $mine -and $_.CommandLine -match '{markers}' "
        "} | Select-Object -ExpandProperty ProcessId"
    )
    pids: set[int] = set()
    for line in _run_powershell(script).splitlines():
        stripped = line.strip()
        if stripped.isdigit():
            pids.add(int(stripped))
    return pids


def _process_parent_map_windows() -> dict[int, int]:
    script = (
        "Get-CimInstance Win32_Process | "
        "ForEach-Object { \"{0},{1}\" -f $_.ProcessId, $_.ParentProcessId }"
    )
    parent_by_pid: dict[int, int] = {}
    for line in _run_powershell(script).splitlines():
        parts = line.strip().split(",", 1)
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        parent_by_pid[int(parts[0])] = int(parts[1])
    return parent_by_pid


def _is_descendant_of(pid: int, ancestor_pids: set[int], parent_by_pid: dict[int, int]) -> bool:
    seen: set[int] = set()
    current = pid
    while current > 0 and current not in seen:
        if current in ancestor_pids:
            return True
        seen.add(current)
        current = parent_by_pid.get(current, 0)
    return False


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
    candidates: list[int] = []
    for line in _run_powershell(script).splitlines():
        stripped = line.strip()
        if stripped.isdigit():
            candidates.append(int(stripped))

    active_agents = _active_figma_flutter_pids_windows()
    active_agents.add(os.getpid())
    parent_by_pid = _process_parent_map_windows()
    stale: list[int] = []
    for pid in candidates:
        if _is_descendant_of(pid, active_agents, parent_by_pid):
            continue
        stale.append(pid)
    return stale


def _active_figma_flutter_pids_unix() -> set[int]:
    proc = subprocess.run(
        ["pgrep", "-f", "figma-flutter|figma_flutter_agent"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: set[int] = {os.getpid()}
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.isdigit():
            pids.add(int(stripped))
    return pids


def _process_parent_map_unix() -> dict[int, int]:
    proc = subprocess.run(
        ["ps", "-eo", "pid=", "ppid="],
        capture_output=True,
        text=True,
        check=False,
    )
    parent_by_pid: dict[int, int] = {}
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            parent_by_pid[int(parts[0])] = int(parts[1])
    return parent_by_pid


def _collect_stale_pids_unix() -> list[int]:
    proc = subprocess.run(
        ["pgrep", "-f", "ast_compiler|dart_ast_sidecar/bin/ast_compiler.dart"],
        capture_output=True,
        text=True,
        check=False,
    )
    candidates: list[int] = []
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.isdigit():
            candidates.append(int(stripped))
    active_agents = _active_figma_flutter_pids_unix()
    parent_by_pid = _process_parent_map_unix()
    return [
        pid
        for pid in candidates
        if pid not in active_agents and not _is_descendant_of(pid, active_agents, parent_by_pid)
    ]


def _cleanup_windows() -> int:
    stale = _collect_stale_pids_windows()
    return _kill_pids_windows(stale)


def _cleanup_unix() -> int:
    stale = _collect_stale_pids_unix()
    killed = 0
    for pid in stale:
        proc = subprocess.run(
            ["kill", "-9", str(pid)],
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
    Does not terminate sidecars owned by another live ``figma-flutter`` session.
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
