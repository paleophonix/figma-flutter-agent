"""Flutter launch and stale web-process cleanup helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.flutter_app_log import (
    FlutterRenderErrorCapture,
    open_render_error_log_stream,
)
from figma_flutter_agent.dev.flutter_sdk import require_flutter_executable
from figma_flutter_agent.dev.preview_size import (
    chrome_preview_dart_defines,
    chrome_preview_window_flags,
    chrome_web_run_flags,
    is_chrome_device,
    prepare_artboard_chrome_launch,
    responsive_config_preview_size,
)
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.generator.render_surface import resolve_chrome_preview_size
from figma_flutter_agent.tools.process_run import (
    FLUTTER_PUB_GET_TIMEOUT_SEC,
    run_interactive_subprocess,
    run_subprocess,
)

if TYPE_CHECKING:
    from figma_flutter_agent.config.models import ResponsiveConfig, ResponsivePreviewMode

_DUAL_PREVIEW_STATIC_WEB_PORT = 7357
_DUAL_PREVIEW_RESPONSIVE_WEB_PORT = 7358
_DUAL_PREVIEW_WINDOW_GAP_PX = 16

LaunchPreviewKind = Literal["static", "responsive"]


def flutter_run_stopped(returncode: int | None) -> bool:
    """Return True when ``flutter run`` was stopped interactively."""
    if returncode in {0, None}:
        return False
    if returncode in {130, 255, 3221225786, -1073741510}:
        return True
    return returncode < 0


def run_flutter_command(
    cmd: list[str],
    *,
    project_dir: Path,
    action: str,
    feature_name: str | None = None,
) -> None:
    """Run a Flutter CLI command and map failures to ``FlutterProjectError``."""
    result = run_subprocess(
        cmd,
        cwd=project_dir,
        label=action,
        timeout_sec=FLUTTER_PUB_GET_TIMEOUT_SEC,
        project_dir=project_dir,
        feature_name=feature_name,
    )
    if result.returncode != 0:
        logger.error("{} failed (exit {})", action, result.returncode)
        msg = f"{action} failed (exit {result.returncode})"
        raise FlutterProjectError(msg)


_FLUTTER_DEVICE_PROFILE_MARKER = "flutter_tools."


def reap_stale_flutter_web_processes() -> int:
    """Terminate leftover Chrome processes from prior ``flutter run`` web sessions."""
    try:
        if sys.platform == "win32":
            count = _reap_stale_flutter_web_windows()
        else:
            count = _reap_stale_flutter_web_posix()
    except Exception:
        logger.exception("Stale Flutter web process cleanup failed; continuing")
        return 0
    if count:
        logger.info("Reaped {} stale Flutter web process(es) before launch", count)
    return count


def _reap_stale_flutter_web_windows() -> int:
    """Kill flutter-web Chrome processes on Windows via a single PowerShell sweep."""
    script = (
        "$ps = @(Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{_FLUTTER_DEVICE_PROFILE_MARKER}*' }}); "
        "foreach ($p in $ps) { try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } "
        "catch {} }; Write-Output $ps.Count"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    return _parse_reaped_count(result.stdout)


def _reap_stale_flutter_web_posix() -> int:
    """Kill flutter-web Chrome processes on macOS/Linux via ``pkill``."""
    before = _count_flutter_web_posix()
    subprocess.run(
        ["pkill", "-f", _FLUTTER_DEVICE_PROFILE_MARKER],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return before


def _count_flutter_web_posix() -> int:
    result = subprocess.run(
        ["pgrep", "-fc", _FLUTTER_DEVICE_PROFILE_MARKER],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return _parse_reaped_count(result.stdout)


def _parse_reaped_count(stdout: str | None) -> int:
    """Parse a process count from sweep stdout; tolerate empty/garbled output."""
    for token in (stdout or "").split():
        if token.isdigit():
            return int(token)
    return 0


def _resolve_preview_launch_mode(
    *,
    settings: Settings | None,
    artboard_preview: bool | None,
) -> ResponsivePreviewMode | Literal["static", "responsive"]:
    """Map config and explicit overrides to a single-window or dual preview plan."""
    if artboard_preview is True:
        return "static"
    if artboard_preview is False:
        return "responsive"
    responsive = settings.agent.responsive if settings is not None else None
    if responsive is None:
        return "static"
    return responsive.mode


def _append_chrome_preview_flags(
    run_cmd: list[str],
    *,
    device_id: str | None,
    preview_size: tuple[int, int] | None,
    preview_kind: LaunchPreviewKind,
    responsive: ResponsiveConfig | None,
    web_port: int | None = None,
    window_offset_x: int = 0,
) -> None:
    """Extend ``flutter run`` argv with Chrome preview flags for one window."""
    if preview_size is None or not is_chrome_device(device_id):
        return
    artboard_width, artboard_height = preview_size
    adaptive = preview_kind == "responsive" and (responsive is not None and responsive.enabled)
    if not adaptive:
        run_cmd.extend(chrome_preview_dart_defines(artboard_width, artboard_height))
    if adaptive and responsive is not None:
        width, height = resolve_chrome_preview_size(
            artboard_width=artboard_width,
            artboard_height=artboard_height,
            responsive=responsive,
        )
        run_cmd.extend(
            chrome_preview_window_flags(
                width,
                height,
                window_offset_x=window_offset_x,
            ),
        )
        logger.info(
            "Chrome adaptive preview artboard {}x{} (responsive shell, window {}x{})",
            artboard_width,
            artboard_height,
            width,
            height,
        )
    else:
        width, height = artboard_width, artboard_height
        run_cmd.extend(
            chrome_preview_window_flags(
                width,
                height,
                window_offset_x=window_offset_x,
            ),
        )
        if preview_kind == "static":
            logger.info("Chrome artboard preview {}x{} (1:1 golden frame)", width, height)
        else:
            logger.info(
                "Chrome live preview {}x{} (artboard shell, scroll enabled)",
                width,
                height,
            )
    if web_port is not None:
        run_cmd.extend(["--web-port", str(web_port)])


def _build_flutter_run_cmd(
    flutter: str,
    *,
    device_id: str | None,
    preview_size: tuple[int, int] | None,
    preview_kind: LaunchPreviewKind,
    responsive: ResponsiveConfig | None,
    web_port: int | None = None,
    window_offset_x: int = 0,
) -> list[str]:
    """Assemble ``flutter run`` argv for one preview window."""
    run_cmd = [flutter, "run", "--no-pub"]
    if device_id:
        run_cmd.extend(["-d", device_id])
    if is_chrome_device(device_id):
        run_cmd.extend(chrome_web_run_flags())
    _append_chrome_preview_flags(
        run_cmd,
        device_id=device_id,
        preview_size=preview_size,
        preview_kind=preview_kind,
        responsive=responsive,
        web_port=web_port,
        window_offset_x=window_offset_x,
    )
    return run_cmd


def _spawn_flutter_run_background(
    run_cmd: list[str],
    *,
    project_dir: Path,
) -> subprocess.Popen[str]:
    """Start ``flutter run`` without attaching interactive logs."""
    return subprocess.Popen(
        run_cmd,
        cwd=project_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _terminate_background_flutter(proc: subprocess.Popen[str] | None) -> None:
    """Stop a background ``flutter run`` started for dual preview."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _run_flutter_interactive(
    run_cmd: list[str],
    *,
    project_dir: Path,
    device_label: str,
    feature_name: str | None,
) -> bool:
    """Run ``flutter run`` with terminal tee and optional render-error log capture."""
    run_label = f"flutter run ({device_label})"
    logger.info("Launching {} in {}", run_label, project_dir.as_posix())

    render_error_stream = (
        open_render_error_log_stream(project_dir=project_dir, feature_name=feature_name)
        if feature_name
        else None
    )
    render_error_capture: FlutterRenderErrorCapture | None = None
    if render_error_stream is not None:
        render_error_capture = FlutterRenderErrorCapture(
            sink=render_error_stream.write_line,
        )

    def _on_flutter_line(line: str) -> None:
        if render_error_capture is not None:
            render_error_capture.feed_flutter_line(line)

    try:
        result = run_interactive_subprocess(
            run_cmd,
            cwd=project_dir,
            label=run_label,
            project_dir=project_dir,
            feature_name=feature_name,
            on_stdout_line=_on_flutter_line,
        )
    finally:
        if render_error_capture is not None:
            render_error_capture.stop()
    if result.returncode != 0:
        if flutter_run_stopped(result.returncode):
            logger.info("Flutter run stopped (exit {})", result.returncode)
            return False
        msg = f"flutter run failed (exit {result.returncode})"
        raise FlutterProjectError(msg)
    return True


def launch_flutter_app(
    project_dir: Path,
    *,
    device_id: str | None = None,
    flutter_sdk: str | Path | None = None,
    preview_size: tuple[int, int] | None = None,
    dump_path: Path | None = None,
    artboard_preview: bool | None = None,
    settings: Settings | None = None,
    feature_name: str | None = None,
) -> bool:
    """Run ``flutter pub get`` and ``flutter run`` in ``project_dir``."""
    configured_size: tuple[int, int] | None = None
    responsive = settings.agent.responsive if settings is not None else None
    if responsive is not None:
        configured_size = responsive_config_preview_size(responsive)
    device_id, preview_size = prepare_artboard_chrome_launch(
        device_id=device_id,
        flutter_sdk=flutter_sdk,
        preview_size=preview_size,
        dump_path=dump_path if preview_size is None else None,
    )
    if preview_size is None and configured_size is not None:
        device_id, preview_size = prepare_artboard_chrome_launch(
            device_id=device_id,
            flutter_sdk=flutter_sdk,
            preview_size=configured_size,
            dump_path=None,
        )
    launch_mode = _resolve_preview_launch_mode(
        settings=settings,
        artboard_preview=artboard_preview,
    )
    reap_stale_flutter_web_processes()
    flutter = require_flutter_executable(sdk_root=flutter_sdk)
    logger.info("Running flutter pub get in {}", project_dir.as_posix())
    run_flutter_command(
        [flutter, "pub", "get"],
        project_dir=project_dir,
        action="flutter pub get",
        feature_name=feature_name,
    )
    device_label = device_id or "default device"

    if launch_mode == "both":
        static_offset = 0
        responsive_offset = 0
        if preview_size is not None:
            responsive_offset = preview_size[0] + _DUAL_PREVIEW_WINDOW_GAP_PX
        static_cmd = _build_flutter_run_cmd(
            flutter,
            device_id=device_id,
            preview_size=preview_size,
            preview_kind="static",
            responsive=responsive,
            web_port=_DUAL_PREVIEW_STATIC_WEB_PORT,
            window_offset_x=static_offset,
        )
        responsive_cmd = _build_flutter_run_cmd(
            flutter,
            device_id=device_id,
            preview_size=preview_size,
            preview_kind="responsive",
            responsive=responsive,
            web_port=_DUAL_PREVIEW_RESPONSIVE_WEB_PORT,
            window_offset_x=responsive_offset,
        )
        logger.info(
            "Dual preview: static window (port {}) + responsive window (port {}, logs)",
            _DUAL_PREVIEW_STATIC_WEB_PORT,
            _DUAL_PREVIEW_RESPONSIVE_WEB_PORT,
        )
        static_proc: subprocess.Popen[str] | None = None
        try:
            static_proc = _spawn_flutter_run_background(
                static_cmd,
                project_dir=project_dir,
            )
            return _run_flutter_interactive(
                responsive_cmd,
                project_dir=project_dir,
                device_label=f"{device_label}, responsive",
                feature_name=feature_name,
            )
        finally:
            _terminate_background_flutter(static_proc)

    preview_kind: LaunchPreviewKind = "static" if launch_mode == "static" else "responsive"
    run_cmd = _build_flutter_run_cmd(
        flutter,
        device_id=device_id,
        preview_size=preview_size,
        preview_kind=preview_kind,
        responsive=responsive,
    )
    return _run_flutter_interactive(
        run_cmd,
        project_dir=project_dir,
        device_label=device_label,
        feature_name=feature_name,
    )
