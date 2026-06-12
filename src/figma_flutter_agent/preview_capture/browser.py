"""Browser backends for fast preview PNG capture."""

from __future__ import annotations

import http.server
import importlib.util
import shutil
import socket
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Iterator, cast

from figma_flutter_agent.errors import FastPreviewUnavailableError
from figma_flutter_agent.preview_capture.models import PreviewScene
from figma_flutter_agent.preview_capture.writer import write_preview_workspace

_PREVIEW_READY_EXPR = "window.__FIGMA_PREVIEW_READY__ === true"


@contextmanager
def serve_preview_workspace(workspace: Path) -> Iterator[str]:
    """Serve a preview workspace over loopback HTTP for headless browser capture."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    handler = partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(workspace.resolve()),
    )
    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/index.html"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def playwright_available() -> bool:
    """Return True when the Playwright Python package is importable."""
    return importlib.util.find_spec("playwright") is not None


def find_chrome_executable() -> str | None:
    """Locate a Chrome or Chromium executable on PATH or common install paths."""
    for name in (
        "chrome",
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
    ):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    local_app = Path.home() / "AppData" / "Local"
    windows_candidates = (
        local_app / "Google" / "Chrome" / "Application" / "chrome.exe",
        local_app / "Chromium" / "Application" / "chrome.exe",
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    )
    for candidate in windows_candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_preview_backend() -> str:
    """Return ``playwright``, ``chrome``, or raise when unavailable."""
    if playwright_available():
        return "playwright"
    if find_chrome_executable() is not None:
        return "chrome"
    msg = (
        "Browser preview backend unavailable. "
        "Install Playwright (`poetry install --with preview` and `playwright install chromium`) "
        "or provide Chrome/Chromium on PATH."
    )
    raise FastPreviewUnavailableError(msg)


def capture_scene_png(
    scene: PreviewScene,
    *,
    timeout_sec: float,
    device_scale_factor: float,
) -> tuple[bytes, str]:
    """Capture a preview scene to PNG bytes.

    Args:
        scene: Scene to render.
        timeout_sec: Browser wait timeout.
        device_scale_factor: Device pixel ratio for Playwright captures.

    Returns:
        Tuple of PNG bytes and backend name.

    Raises:
        FastPreviewUnavailableError: When no browser backend is available.
    """
    backend = resolve_preview_backend()
    with tempfile.TemporaryDirectory(prefix="figma-preview-") as tmp:
        workspace = Path(tmp)
        write_preview_workspace(scene, workspace)
        with serve_preview_workspace(workspace) as page_url:
            if backend == "playwright":
                return _capture_with_playwright(
                    page_url,
                    scene=scene,
                    timeout_sec=timeout_sec,
                    device_scale_factor=device_scale_factor,
                ), backend
            return _capture_with_chrome(
                page_url,
                scene=scene,
                workspace=workspace,
                timeout_sec=timeout_sec,
            ), backend


def _capture_with_playwright(
    page_url: str,
    *,
    scene: PreviewScene,
    timeout_sec: float,
    device_scale_factor: float,
) -> bytes:
    from playwright.sync_api import sync_playwright

    timeout_ms = max(int(timeout_sec * 1000), 1000)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": scene.width, "height": scene.height},
                device_scale_factor=device_scale_factor,
            )
            page.goto(page_url, wait_until="load", timeout=timeout_ms)
            page.wait_for_function(_PREVIEW_READY_EXPR, timeout=timeout_ms)
            return cast(bytes, page.screenshot(type="png", full_page=False))
        finally:
            browser.close()


def _capture_with_chrome(
    page_url: str,
    *,
    scene: PreviewScene,
    workspace: Path,
    timeout_sec: float,
) -> bytes:
    chrome = find_chrome_executable()
    if chrome is None:
        msg = "Chrome/Chromium executable not found for preview capture"
        raise FastPreviewUnavailableError(msg)
    output_path = workspace / "capture.png"
    budget_ms = max(int(timeout_sec * 1000), 2000)
    command = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        f"--window-size={scene.width},{scene.height}",
        f"--virtual-time-budget={budget_ms}",
        f"--screenshot={output_path}",
        page_url,
    ]
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=max(timeout_sec, 1.0),
        )
    except subprocess.TimeoutExpired as exc:
        msg = f"Chrome preview capture timed out after {timeout_sec:.0f}s"
        raise FastPreviewUnavailableError(msg) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        msg = f"Chrome preview capture failed: {stderr or exc}"
        raise FastPreviewUnavailableError(msg) from exc
    if not output_path.is_file():
        msg = "Chrome preview capture did not produce a PNG"
        raise FastPreviewUnavailableError(msg)
    return output_path.read_bytes()
