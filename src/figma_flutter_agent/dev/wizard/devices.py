"""Flutter device helpers for the wizard."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from loguru import logger

from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable

_AUTO_FLUTTER_DEVICE_TOKENS = frozenset({"", "auto", "chrome"})
_DEFAULT_FLUTTER_DEVICE_TOKENS = frozenset({"default", "system"})


def list_flutter_devices(*, flutter_sdk: str | Path | None = None) -> list[tuple[str, str]]:
    """Return Flutter device ids and labels from ``flutter devices --machine``."""
    flutter = resolve_flutter_executable(sdk_root=flutter_sdk)
    if flutter is None:
        return []

    result = subprocess.run(
        [flutter, "devices", "--machine"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            payload = json.loads(result.stdout)
            devices: list[tuple[str, str]] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                device_id = item.get("id")
                if not device_id:
                    continue
                name = str(item.get("name") or device_id)
                platform = str(item.get("targetPlatform") or item.get("platform") or "unknown")
                devices.append((str(device_id), f"{name} ({platform})"))
            if devices:
                return devices
        except json.JSONDecodeError:
            logger.debug("Could not parse flutter devices --machine output")

    fallback = subprocess.run(
        [flutter, "devices"],
        capture_output=True,
        text=True,
        check=False,
    )
    if fallback.returncode != 0:
        return []

    devices = []
    for line in fallback.stdout.splitlines():
        match = re.match(r"^\s*(.+?) \(mobile|desktop|web\)\s•\s(.+?) •", line)
        if match:
            devices.append((match.group(2).strip(), match.group(1).strip()))
    return devices


def device_id_from_choice(label: str) -> str | None:
    """Extract a Flutter device id from a wizard choice label."""
    match = re.search(r"\[(.+?)\]\s*$", label)
    if match:
        return match.group(1)
    return None


def default_flutter_device_option(devices: list[tuple[str, str]]) -> str | None:
    """Return the wizard menu label for the preferred default ``flutter run`` target."""
    if not devices:
        return None

    def option(device_id: str, label: str) -> str:
        return f"{label} [{device_id}]"

    for device_id, label in devices:
        lowered_id = device_id.lower()
        lowered_label = label.lower()
        if lowered_id == "chrome" or (
            "chrome" in lowered_label and "web-javascript" in lowered_label
        ):
            return option(device_id, label)

    for device_id, label in devices:
        if "web-javascript" in label.lower():
            return option(device_id, label)

    device_id, label = devices[0]
    return option(device_id, label)


def resolve_flutter_device_id(
    *,
    flutter_sdk: str | Path | None = None,
    configured: str | None = None,
) -> str | None:
    """Resolve ``flutter run -d`` from YAML ``runtime.flutter_device_id``.

    Args:
        flutter_sdk: Optional Flutter SDK root when not on PATH.
        configured: Value from ``runtime.flutter_device_id`` (``None`` when unset).

    Returns:
        Device id string, or ``None`` when Flutter should pick the default target.
    """
    if configured is not None:
        token = configured.strip()
        lowered = token.lower()
        if lowered in _DEFAULT_FLUTTER_DEVICE_TOKENS:
            return None
        if token and lowered not in _AUTO_FLUTTER_DEVICE_TOKENS:
            return token

    devices = list_flutter_devices(flutter_sdk=flutter_sdk)
    option = default_flutter_device_option(devices)
    if option is None:
        return None
    return device_id_from_choice(option)


def resolve_flutter_device_id_from_settings(settings: object) -> str | None:
    """Resolve ``flutter run -d`` using ``Settings.agent.runtime.flutter_device_id``."""
    from figma_flutter_agent.config.settings import Settings

    if not isinstance(settings, Settings):
        msg = "settings must be a Settings instance"
        raise TypeError(msg)
    return resolve_flutter_device_id(
        flutter_sdk=settings.flutter_sdk or None,
        configured=settings.agent.runtime.flutter_device_id,
    )
