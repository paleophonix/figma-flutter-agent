"""Flutter device helpers for the wizard."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from loguru import logger

from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable


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
