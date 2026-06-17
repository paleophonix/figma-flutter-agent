"""Infer Figma artboard dimensions for Chrome dev preview window sizing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from figma_flutter_agent.config.models import ResponsiveConfig

_DEFAULT_ARTBOARD_SIZE = (390, 844)
ARTBOARD_PREVIEW_WIDTH_DEFINE = "FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH"
ARTBOARD_PREVIEW_HEIGHT_DEFINE = "FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT"
ARTBOARD_CAPTURE_MODE_DEFINE = "FIGMA_FLUTTER_ARTBOARD_CAPTURE_MODE"
CHROME_PREVIEW_WEB_HOST = "127.0.0.1"


def infer_artboard_size_from_dump(
    dump_path: Path,
    *,
    default: tuple[int, int] = _DEFAULT_ARTBOARD_SIZE,
) -> tuple[int, int]:
    """Return rounded artboard width/height from a raw or processed layout dump.

    Args:
        dump_path: Cached Figma subtree JSON (``.debug/raw`` or processed).
        default: Fallback when width/height cannot be resolved.

    Returns:
        ``(width, height)`` in logical pixels.
    """
    if not dump_path.is_file():
        return default
    try:
        payload = json.loads(dump_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    resolved = _artboard_size_from_payload(payload)
    return resolved if resolved is not None else default


def chrome_preview_window_flags(
    width: int,
    height: int,
    *,
    set_window_size: bool = True,
    window_offset_x: int = 0,
    window_offset_y: int = 0,
) -> list[str]:
    """Build safe Chrome flags for Flutter web preview.

    Args:
        width: Target preview width in logical pixels (unused; app dart-defines
            provide the reliable artboard size).
        height: Target preview height in logical pixels (unused; app dart-defines
            provide the reliable artboard size).
        set_window_size: Retained for API compatibility; window sizing is skipped
            because comma-separated ``--window-size`` flags can be misread as URLs.
        window_offset_x: Optional Chrome window horizontal offset for dual preview.
        window_offset_y: Optional Chrome window vertical offset for dual preview.

    Returns:
        ``--web-browser-flag`` entries for ``flutter run -d chrome``.
    """
    _ = (width, height, set_window_size)
    flags = [
        "--web-browser-flag=--hide-scrollbars",
        "--web-browser-flag=--disable-infobars",
        "--web-browser-flag=--disable-extensions",
    ]
    if window_offset_x or window_offset_y:
        flags.append(
            f"--web-browser-flag=--window-position={window_offset_x},{window_offset_y}",
        )
    return flags


def open_preview_browser(url: str) -> bool:
    """Open a Flutter web preview URL in the system default browser.

    Args:
        url: Browser-navigable preview URL (for example from
            :func:`chrome_preview_web_url`).

    Returns:
        True when the OS browser launcher accepts the request.
    """
    import webbrowser

    return webbrowser.open(url, new=1, autoraise=True)


def chrome_preview_web_url(port: int) -> str:
    """Return a browser-navigable Flutter web dev-server URL for wizard preview.

    Args:
        port: ``--web-port`` passed to ``flutter run``.

    Returns:
        ``http://127.0.0.1:<port>`` — IPv4 loopback so Windows Chrome does not
        resolve ``localhost`` to a different address than the Flutter bind.
    """
    safe_port = max(int(port), 1)
    return f"http://{CHROME_PREVIEW_WEB_HOST}:{safe_port}"


def chrome_preview_web_launch_url(port: int) -> str:
    """Return the ``--web-launch-url`` passed to ``flutter run`` for Chrome devices.

    Args:
        port: ``--web-port`` passed to ``flutter run``.

    Returns:
        Preview origin with trailing slash (Flutter default path is ``/``).
    """
    return f"{chrome_preview_web_url(port)}/"


def chrome_web_run_flags() -> list[str]:
    """Bundle CanvasKit/Skwasm locally and bind a browser-navigable web hostname.

    Wizard Chrome preview must start when CDN access is blocked (VPN, adblock,
    corporate proxy). Flutter 3.22+ exposes this as ``--no-web-resources-cdn``.

    ``--web-hostname=127.0.0.1`` avoids both ``0.0.0.0`` URLs that Edge/Chrome
    reject with ``ERR_ADDRESS_INVALID`` and ``localhost`` binds that listen only
    on ``[::1]`` while the browser connects via ``127.0.0.1`` on Windows.
    """
    return ["--no-web-resources-cdn", f"--web-hostname={CHROME_PREVIEW_WEB_HOST}"]


def chrome_preview_dart_defines(
    width: int,
    height: int,
    *,
    capture_mode: bool = False,
) -> list[str]:
    """Pass artboard size into Flutter so preview shell/layout skip web margins.

    Args:
        width: Artboard width in logical pixels.
        height: Artboard height in logical pixels.
        capture_mode: When true, enable fixed artboard clipping for golden capture.

    Returns:
        ``--dart-define`` entries paired with :func:`chrome_preview_window_flags`.
    """
    safe_w = max(int(width), 1)
    safe_h = max(int(height), 1)
    defines = [
        f"--dart-define={ARTBOARD_PREVIEW_WIDTH_DEFINE}={safe_w}",
        f"--dart-define={ARTBOARD_PREVIEW_HEIGHT_DEFINE}={safe_h}",
    ]
    if capture_mode:
        defines.append(f"--dart-define={ARTBOARD_CAPTURE_MODE_DEFINE}=1")
    return defines


def chrome_preview_launch_flags(width: int, height: int) -> list[str]:
    """Chrome window flags plus Dart defines for a 1:1 Figma artboard preview."""
    return [
        *chrome_preview_window_flags(width, height),
        *chrome_preview_dart_defines(width, height),
    ]


def chrome_live_launch_flags(width: int, height: int) -> list[str]:
    """Chrome flags for interactive dev preview at Figma artboard dimensions.

    Interactive Chrome must not pass artboard dart-defines: those activate the
    fixed preview branch and suppress vertical scroll on tall screens. Golden
    capture passes defines separately with ``capture_mode=True``.
    """
    return chrome_preview_window_flags(width, height)


def chrome_adaptive_launch_flags(width: int, height: int) -> list[str]:
    """Chrome flags for wide responsive preview (no artboard dart-defines)."""
    return chrome_preview_window_flags(width, height, set_window_size=True)


def is_chrome_device(device_id: str | None) -> bool:
    """Return True when ``device_id`` targets a Chrome/Chromium web preview."""
    if not device_id:
        return False
    lowered = device_id.lower()
    return "chrome" in lowered or lowered in {"web-server", "edge"}


def responsive_config_preview_size(
    responsive: ResponsiveConfig,
) -> tuple[int, int] | None:
    """Return Chrome preview size from YAML when both dimensions are configured."""
    if responsive.preview_width is None or responsive.preview_height is None:
        return None
    return int(responsive.preview_width), int(responsive.preview_height)


def resolve_default_chrome_device_id(*, flutter_sdk: str | Path | None = None) -> str | None:
    """Return Chrome ``device_id`` when Flutter lists a web-javascript target.

    Args:
        flutter_sdk: Optional Flutter SDK root when not on PATH.

    Returns:
        Chrome device id, or ``None`` when unavailable.
    """
    from figma_flutter_agent.dev.wizard import (
        default_flutter_device_option,
        device_id_from_choice,
        list_flutter_devices,
    )

    devices = list_flutter_devices(flutter_sdk=flutter_sdk)
    option = default_flutter_device_option(devices)
    if option is None:
        return None
    return device_id_from_choice(option)


def prepare_artboard_chrome_launch(
    *,
    device_id: str | None,
    flutter_sdk: str | Path | None,
    preview_size: tuple[int, int] | None = None,
    dump_path: Path | None = None,
) -> tuple[str | None, tuple[int, int] | None]:
    """Resolve wizard defaults: Chrome target and artboard window size from dump.

    Args:
        device_id: Explicit ``flutter run -d`` target, if any.
        flutter_sdk: Optional Flutter SDK root when not on PATH.
        preview_size: Optional artboard size override.
        dump_path: Cached layout dump used to infer artboard size.

    Returns:
        ``(device_id, preview_size)`` after applying wizard preview defaults.
    """
    resolved_size = preview_size
    if resolved_size is None and dump_path is not None:
        resolved_size = infer_artboard_size_from_dump(dump_path)
    if resolved_size is None:
        return device_id, None
    resolved_device = device_id
    if resolved_device is None:
        resolved_device = resolve_default_chrome_device_id(flutter_sdk=flutter_sdk)
    return resolved_device, resolved_size


def _artboard_size_from_payload(payload: Any) -> tuple[int, int] | None:
    if not isinstance(payload, dict):
        return None
    clean_tree = payload.get("cleanTree")
    if isinstance(clean_tree, dict):
        resolved = _size_from_sizing(clean_tree.get("sizing"))
        if resolved is not None:
            return resolved
    bounds = payload.get("absoluteBoundingBox")
    if isinstance(bounds, dict):
        resolved = _size_from_bounds(bounds)
        if resolved is not None:
            return resolved
    return None


def _size_from_sizing(sizing: Any) -> tuple[int, int] | None:
    if not isinstance(sizing, dict):
        return None
    return _pair_from_values(sizing.get("width"), sizing.get("height"))


def _size_from_bounds(bounds: dict[str, Any]) -> tuple[int, int] | None:
    return _pair_from_values(bounds.get("width"), bounds.get("height"))


def _pair_from_values(width: Any, height: Any) -> tuple[int, int] | None:
    try:
        if width is None or height is None:
            return None
        w = int(round(float(width)))
        h = int(round(float(height)))
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return w, h
