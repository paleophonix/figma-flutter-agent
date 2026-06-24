"""Colocated Flutter web preview server management."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path

from loguru import logger

from figma_flutter_agent.dev.flutter_launch import _build_flutter_run_cmd, wait_for_tcp_listen
from figma_flutter_agent.dev.flutter_sdk import require_flutter_executable
from figma_flutter_agent.dev.preview_size import CHROME_PREVIEW_WEB_HOST
from figma_flutter_agent.errors import FigmaFlutterError

_PREVIEW_PROCS: dict[str, subprocess.Popen[str]] = {}


def _session_key(project_dir: Path, mode: str, job_id: str) -> str:
    return f"{project_dir.as_posix()}:{mode}:{job_id}"


def _preview_stderr_path(project_dir: Path, mode: str) -> Path:
    cache = project_dir / ".figma-flutter" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    return cache / f"preview_{mode}.stderr.log"


def _tail_text(path: Path, *, max_bytes: int = 4096) -> str:
    if not path.is_file():
        return ""
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="replace").strip()


def _is_preview_listening(port: int) -> bool:
    try:
        with socket.create_connection((CHROME_PREVIEW_WEB_HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


def ensure_flutter_web_support(project_dir: Path) -> None:
    """Ensure the Flutter project can build for web preview."""
    if (project_dir / "web").is_dir():
        return
    flutter = require_flutter_executable(sdk_root=None)
    logger.info("Adding web platform support for preview in {}", project_dir.as_posix())
    completed = subprocess.run(
        [flutter, "create", ".", "--platforms=web"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        msg = f"flutter create --platforms=web failed for {project_dir}: {detail[:500]}"
        raise FigmaFlutterError(msg)


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
    job_id = str(sidecar.get("jobId") or "")
    if mode == "fixed":
        port = int(sidecar.get("staticPort") or 17357)
        preview_kind = "static"
    else:
        port = int(sidecar.get("adaptivePort") or 17358)
        preview_kind = "responsive"

    key = _session_key(project_dir, mode, job_id)
    existing = _PREVIEW_PROCS.get(key)
    if existing is not None and existing.poll() is None:
        if _is_preview_listening(port):
            return port
        logger.warning(
            "Stale preview process for {} mode={}; restarting on port {}",
            project_dir.as_posix(),
            mode,
            port,
        )
        existing.kill()
        _PREVIEW_PROCS.pop(key, None)

    ensure_flutter_web_support(project_dir)
    flutter = require_flutter_executable(sdk_root=None)
    web_base_href = f"/preview/{job_id}/" if job_id else None
    run_cmd = _build_flutter_run_cmd(
        flutter,
        device_id="web-server",
        preview_size=(390, 844),
        preview_kind=preview_kind,  # type: ignore[arg-type]
        responsive=None,
        web_port=port,
        web_base_href=web_base_href,
    )
    stderr_path = _preview_stderr_path(project_dir, mode)
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        run_cmd,
        cwd=project_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=stderr_handle,
        text=True,
    )
    stderr_handle.close()
    if not wait_for_tcp_listen(CHROME_PREVIEW_WEB_HOST, port, proc=proc):
        exit_code = proc.poll()
        proc.kill()
        detail = _tail_text(stderr_path)
        raise FigmaFlutterError(
            f"Flutter preview failed to listen on port {port}"
            + (f" (exit={exit_code})" if exit_code is not None else "")
            + (f": {detail}" if detail else "")
        )
    _PREVIEW_PROCS[key] = proc
    logger.info(
        "Flutter preview listening on http://{}:{}/ for {} ({})",
        CHROME_PREVIEW_WEB_HOST,
        port,
        project_dir.as_posix(),
        mode,
    )
    return port
