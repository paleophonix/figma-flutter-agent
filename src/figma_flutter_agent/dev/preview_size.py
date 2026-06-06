"""Infer Figma artboard dimensions for Chrome dev preview window sizing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_ARTBOARD_SIZE = (390, 844)
ARTBOARD_PREVIEW_WIDTH_DEFINE = "FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH"
ARTBOARD_PREVIEW_HEIGHT_DEFINE = "FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT"


def infer_artboard_size_from_dump(
    dump_path: Path,
    *,
    default: tuple[int, int] = _DEFAULT_ARTBOARD_SIZE,
) -> tuple[int, int]:
    """Return rounded artboard width/height from a raw or processed layout dump.

    Args:
        dump_path: Cached Figma subtree JSON (``.figma_debug/raw`` or processed).
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


def chrome_preview_window_flags(width: int, height: int) -> list[str]:
    """Build safe ``flutter run`` Chrome flags for artboard preview.

    Args:
        width: Artboard width in logical pixels (unused; sizing is via dart-defines).
        height: Artboard height in logical pixels (unused; sizing is via dart-defines).

    Returns:
        ``--web-browser-flag`` entries for ``flutter run -d chrome``.

    Note:
        Do not pass ``--window-size=W,H`` or ``--window-position=X,Y`` here. Chromium
        treats the segment after the comma as a navigation URL (e.g. height ``932``
        opens ``0.0.3.164``). Artboard dimensions are applied in-app via
        :func:`chrome_preview_dart_defines`.
    """
    _ = (width, height)
    return [
        "--web-browser-flag=--hide-scrollbars",
        "--web-browser-flag=--disable-infobars",
        "--web-browser-flag=--disable-extensions",
    ]


def chrome_preview_dart_defines(width: int, height: int) -> list[str]:
    """Pass artboard size into Flutter so preview shell/layout skip web margins.

    Args:
        width: Artboard width in logical pixels.
        height: Artboard height in logical pixels.

    Returns:
        ``--dart-define`` entries paired with :func:`chrome_preview_window_flags`.
    """
    safe_w = max(int(width), 1)
    safe_h = max(int(height), 1)
    return [
        f"--dart-define={ARTBOARD_PREVIEW_WIDTH_DEFINE}={safe_w}",
        f"--dart-define={ARTBOARD_PREVIEW_HEIGHT_DEFINE}={safe_h}",
    ]


def chrome_preview_launch_flags(width: int, height: int) -> list[str]:
    """Chrome window flags plus Dart defines for a 1:1 Figma artboard preview."""
    return [
        *chrome_preview_window_flags(width, height),
        *chrome_preview_dart_defines(width, height),
    ]


def is_chrome_device(device_id: str | None) -> bool:
    """Return True when ``device_id`` targets a Chrome/Chromium web preview."""
    if not device_id:
        return False
    lowered = device_id.lower()
    return "chrome" in lowered or lowered in {"web-server", "edge"}


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
