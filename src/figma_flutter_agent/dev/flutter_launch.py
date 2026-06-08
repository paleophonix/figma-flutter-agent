"""Flutter launch and stale web-process cleanup helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from loguru import logger

from figma_flutter_agent.dev.flutter_sdk import require_flutter_executable
from figma_flutter_agent.dev.preview_size import (
    chrome_live_launch_flags,
    chrome_preview_launch_flags,
    is_chrome_device,
    prepare_artboard_chrome_launch,
)
from figma_flutter_agent.errors import FlutterProjectError


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
) -> None:
    """Run a Flutter CLI command and map failures to ``FlutterProjectError``."""
    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
    except subprocess.CalledProcessError as exc:
        logger.error("{} failed (exit {})", action, exc.returncode)
        msg = f"{action} failed (exit {exc.returncode})"
        raise FlutterProjectError(msg) from exc


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


def launch_flutter_app(
    project_dir: Path,
    *,
    device_id: str | None = None,
    flutter_sdk: str | Path | None = None,
    preview_size: tuple[int, int] | None = None,
    dump_path: Path | None = None,
    artboard_preview: bool = False,
) -> bool:
    """Run ``flutter pub get`` and ``flutter run`` in ``project_dir``."""
    device_id, preview_size = prepare_artboard_chrome_launch(
        device_id=device_id,
        flutter_sdk=flutter_sdk,
        preview_size=preview_size,
        dump_path=dump_path,
    )
    reap_stale_flutter_web_processes()
    flutter = require_flutter_executable(sdk_root=flutter_sdk)
    logger.info("Running flutter pub get in {}", project_dir.as_posix())
    run_flutter_command(
        [flutter, "pub", "get"],
        project_dir=project_dir,
        action="flutter pub get",
    )
    run_cmd = [flutter, "run", "--no-pub"]
    if device_id:
        run_cmd.extend(["-d", device_id])
    if preview_size is not None and is_chrome_device(device_id):
        width, height = preview_size
        if artboard_preview:
            run_cmd.extend(chrome_preview_launch_flags(width, height))
            logger.info("Chrome artboard preview {}x{} (1:1 golden frame)", width, height)
        else:
            run_cmd.extend(chrome_live_launch_flags(width, height))
            logger.info(
                "Chrome live preview {}x{} (responsive shell, scroll enabled)",
                width,
                height,
            )
    device_label = device_id or "default device"
    logger.info("Launching flutter run on {} in {}", device_label, project_dir.as_posix())
    try:
        subprocess.run(run_cmd, cwd=project_dir, check=True)
    except subprocess.CalledProcessError as exc:
        if flutter_run_stopped(exc.returncode):
            logger.info("Flutter run stopped (exit {})", exc.returncode)
            return False
        msg = f"flutter run failed (exit {exc.returncode})"
        raise FlutterProjectError(msg) from exc
    return True
