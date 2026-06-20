"""Colocated Flutter web preview server management."""

from __future__ import annotations

import subprocess
from pathlib import Path

from figma_flutter_agent.dev.flutter_launch import _build_flutter_run_cmd, wait_for_tcp_listen
from figma_flutter_agent.dev.flutter_sdk import require_flutter_executable
from figma_flutter_agent.dev.preview_size import CHROME_PREVIEW_WEB_HOST
from figma_flutter_agent.errors import FigmaFlutterError

_PREVIEW_PROCS: dict[str, subprocess.Popen[str]] = {}


def _session_key(project_dir: Path, mode: str) -> str:
    return f"{project_dir.as_posix()}:{mode}"


def ensure_flutter_preview_server(
    *,
    project_dir: Path,
    mode: str,
) -> int:
    """Start or reuse a Flutter web-server preview for one sandbox.

    Args:
        project_dir: Flutter project root with ``preview-session.json``.
        mode: ``fixed`` or ``adaptive``.

    Returns:
        Local TCP port serving the preview.

    Raises:
        FigmaFlutterError: When sidecar metadata is missing or launch fails.
    """
    from control_panel.companion.daemon import load_sidecar

    sidecar = load_sidecar(project_dir)
    if mode == "fixed":
        port = int(sidecar.get("staticPort") or 17357)
        preview_kind = "static"
    else:
        port = int(sidecar.get("adaptivePort") or 17358)
        preview_kind = "responsive"

    key = _session_key(project_dir, mode)
    existing = _PREVIEW_PROCS.get(key)
    if existing is not None and existing.poll() is None:
        return port

    flutter = require_flutter_executable(sdk_root=None)
    run_cmd = _build_flutter_run_cmd(
        flutter,
        device_id="web-server",
        preview_size=(390, 844),
        preview_kind=preview_kind,  # type: ignore[arg-type]
        responsive=None,
        web_port=port,
    )
    proc = subprocess.Popen(
        run_cmd,
        cwd=project_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if not wait_for_tcp_listen(CHROME_PREVIEW_WEB_HOST, port, proc=proc):
        proc.kill()
        raise FigmaFlutterError(f"Flutter preview failed to listen on port {port}")
    _PREVIEW_PROCS[key] = proc
    return port
